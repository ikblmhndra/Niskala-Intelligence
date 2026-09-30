#!/usr/bin/env python3
"""Probe: apakah sebuah model di gateway LLM (mis. 9router) bisa ngikutin
instruksi JSON pipeline enrichment, atau malah "ngeles" kayak persona Kiro.

Latar belakang: gateway dev pernah ngebalikin respons dari persona lain
("Kiro") yang nolak format JSON -> `classify()`/`extract_ttps()` gagal
`JSONDecodeError` terus (lihat docs/PROGRESS.md Fase 7.3). Script ini
nge-tes SATU per SATU model di gateway pakai panggilan yang SAMA PERSIS
dengan produksi:

  - prompt system + parameter (`temperature=0`, `response_format=json_object`,
    `max_tokens` 3000/2000) diimpor langsung dari `cti_enrich.stages.classify`
    dan `extract_ttps` -- bukan salinan, jadi gak bisa drift;
  - parser = `cti_core.llm.client.parse_json_response` (yang dipakai pipeline);
  - `max_retries=0` di client OpenAI, supaya yang keukur keandalan SATU
    percobaan. Produksi nyoba sampai 3x, jadi script ini juga ngitung
    perkiraan peluang gagal SETELAH 3 percobaan: (1 - p)^3.

Tiap model dites dengan 4 input tetap (x `--runs` ulangan): judul jelas
cyber, judul non-cyber, judul yang mengandung kata "JSON" (regresi bug lama
`.replace("json","")`), dan ringkasan buat ekstraksi TTP.

Pakai (dari root repo):

    uv run python tools/llm/probe_json.py --list
    uv run python tools/llm/probe_json.py --model my-combo
    uv run python tools/llm/probe_json.py --model kr/claude-sonnet --model gc/gemini --runs 5
    uv run python tools/llm/probe_json.py --all --save-raw /tmp/probe

Kredensial: `LLM__URL` + `LLM__API_KEY` dari env, atau otomatis dari `.env`
(lewat settings aplikasi) kalau gak diset. Key TIDAK pernah dicetak.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import openai
from cti_core.llm.client import parse_json_response
from cti_enrich.stages.classify import _MAX_TOKENS as CLASSIFY_MAX_TOKENS
from cti_enrich.stages.classify import _PROMPT as CLASSIFY_PROMPT
from cti_enrich.stages.extract_ttps import _MAX_TOKENS as TTP_MAX_TOKENS
from cti_enrich.stages.extract_ttps import _TTP_SYSTEM_PROMPT
from cti_enrich.stages.llm_messages import build_messages
from openai import OpenAI

PROD_ATTEMPTS = 3
"""`_MAX_ATTEMPTS` di classify.py / extract_ttps.py."""

# --- input tetap -----------------------------------------------------------

TTP_SUMMARY = (
    "The attackers sent spear-phishing emails with a malicious Word attachment. "
    "Opening it launched a PowerShell script that downloaded a second-stage loader. "
    "The operators then dumped credentials from LSASS memory and moved laterally "
    "over SMB, before exfiltrating data to a command-and-control server over HTTPS."
)


@dataclass(frozen=True)
class Sample:
    name: str
    kind: str  # "classify" | "ttp"
    system: str
    user: str
    max_tokens: int
    expect: dict[str, Any] = field(default_factory=dict)  # cek semantik (cuma warning)


SAMPLES = [
    Sample(
        "classify_cyber",
        "classify",
        CLASSIFY_PROMPT,
        "LockBit ransomware gang claims attack on Bank Syariah Indonesia, leaks 1.5TB of data",
        CLASSIFY_MAX_TOKENS,
        {"related_cyber": True},
    ),
    Sample(
        "classify_noncyber",
        "classify",
        CLASSIFY_PROMPT,
        "Acme launches new flagship smartphone with 200MP camera and faster charging",
        CLASSIFY_MAX_TOKENS,
        {"related_cyber": False},
    ),
    Sample(
        "classify_json_word",
        "classify",
        CLASSIFY_PROMPT,
        "New JSON Web Token flaw lets attackers forge admin sessions",
        CLASSIFY_MAX_TOKENS,
        {"related_cyber": True},
    ),
    # Dua judul ASLI yang memicu persona "Kiro" di gateway dev (e2e staging Fase 10:
    # `claude-haiku-4.5` lewat backend Kiro njawab prosa -- sifatnya bergantung ke isi
    # judul, jadi 4 input generik di atas TIDAK menangkapnya).
    Sample(
        "classify_kiro_1",
        "classify",
        CLASSIFY_PROMPT,
        "Keyword lists: Stop re-entering the same organizational context across every workflow",
        CLASSIFY_MAX_TOKENS,
    ),
    Sample(
        "classify_kiro_2",
        "classify",
        CLASSIFY_PROMPT,
        "EclecticIQ MCP Server: Connect your AI agents directly to your threat intelligence",
        CLASSIFY_MAX_TOKENS,
    ),
    Sample("ttp", "ttp", _TTP_SYSTEM_PROMPT, TTP_SUMMARY, TTP_MAX_TOKENS, {"has_techniques": True}),
]


def samples_from_titles(path: Path) -> list[Sample]:
    """Judul tambahan dari file (satu per baris) -- buat mereplay judul asli yang
    gagal di produksi. Diklasifikasi persis kayak `classify()`."""
    lines = [ln.strip() for ln in path.read_text().splitlines() if ln.strip()]
    return [
        Sample(f"custom_{i}", "classify", CLASSIFY_PROMPT, title, CLASSIFY_MAX_TOKENS)
        for i, title in enumerate(lines, 1)
    ]


# --- grading ---------------------------------------------------------------

PERSONA_RE = re.compile(
    r"\bkiro\b|\bas an ai\b|\blanguage model\b|"
    r"\bi(?:'m| am) (?:sorry|unable|not able)\b|\bi (?:can(?:'|no)t|cannot|won't) |"
    r"\bcannot (?:assist|help|comply)\b",
    re.IGNORECASE,
)
TECHNIQUE_ID_RE = re.compile(r"^T\d{4}(\.\d{3})?$")

# Kolom yang `classify()` baca pakai `data.get(...)`: tipe salah = crash atau
# (lebih buruk) salah diam-diam -- `bool("false")` itu True!
CLASSIFY_FIELDS: dict[str, tuple[type, ...]] = {
    "related_cyber": (bool,),
    "confidence": (int, float),
    "reason": (str,),
    "industries_impacted": (list,),
    "security_tech_best_practice": (bool,),
    "victim_countries": (list,),
    "actor_countries": (list,),
    "confirmed_incident": (bool, type(None)),
    "incident_confidence": (int, float, type(None)),
    "incident_indicators": (list,),
    "victim_name": (str, type(None)),
}
CRITICAL_CLASSIFY = ("related_cyber",)


def _type_ok(value: Any, types: tuple[type, ...]) -> bool:
    # bool subclass int di Python: `True` bukan angka yang valid buat "confidence".
    if isinstance(value, bool) and bool not in types:
        return False
    return isinstance(value, types)


def check_schema(kind: str, data: dict[str, Any]) -> tuple[bool, list[str]]:
    """(ok, catatan). `ok=False` = pipeline bakal crash/salah. Catatan buat
    kolom opsional yang hilang cuma warning -- kode produksi pakai default."""
    notes: list[str] = []
    if kind == "classify":
        for key, types in CLASSIFY_FIELDS.items():
            if key not in data:
                if key in CRITICAL_CLASSIFY:
                    return False, [f"kolom wajib hilang: {key}"]
                notes.append(f"kolom hilang: {key}")
            elif not _type_ok(data[key], types):
                return False, [f"tipe {key} salah: {type(data[key]).__name__} ({data[key]!r:.40})"]
        return True, notes

    if not isinstance(data.get("has_techniques"), bool):
        return False, [f"has_techniques bukan bool: {data.get('has_techniques')!r:.40}"]
    techniques = data.get("techniques", [])
    if not isinstance(techniques, list):
        return False, ["techniques bukan list"]
    for i, t in enumerate(techniques):
        if not isinstance(t, dict) or "technique_id" not in t or "technique_name" not in t:
            return False, [
                f"techniques[{i}] gak punya technique_id/technique_name"
            ]  # KeyError di prod
        if not TECHNIQUE_ID_RE.match(str(t["technique_id"])):
            notes.append(f"ID aneh: {t['technique_id']}")
    return True, notes


@dataclass
class CallResult:
    sample: str
    mode: str  # "json_object" | "plain"
    category: str  # ok | persona | truncated | empty | not_json | bad_schema | timeout | ...
    latency_s: float
    served_by: str | None = None
    finish_reason: str | None = None
    tokens: int | None = None
    notes: list[str] = field(default_factory=list)
    snippet: str = ""
    raw: str = ""

    @property
    def ok(self) -> bool:
        return self.category == "ok"


def grade(sample: Sample, content: Any, finish_reason: str | None) -> tuple[str, list[str]]:
    """Kategori + catatan untuk SATU respons yang sukses diterima."""
    if isinstance(content, str) and not content.strip():
        return ("truncated" if finish_reason == "length" else "empty"), []
    if content is None:
        return "empty", []
    try:
        data = parse_json_response(content)
    except json.JSONDecodeError:
        if finish_reason == "length":
            return "truncated", ["kepotong max_tokens (kemungkinan `<think>` kepanjangan)"]
        if isinstance(content, str) and PERSONA_RE.search(content):
            return "persona", ["jawab pakai prosa/persona, bukan JSON"]
        return "not_json", []

    ok, notes = check_schema(sample.kind, data)
    if not ok:
        return "bad_schema", notes
    for key, want in sample.expect.items():
        if data.get(key) != want:
            notes.append(f"semantik: {key}={data.get(key)!r}, diharapkan {want!r}")
    return "ok", notes


def call_once(
    client: OpenAI,
    model: str,
    sample: Sample,
    mode: str,
    *,
    timeout: float,
    hardened: bool = False,
) -> CallResult:
    kwargs: dict[str, Any] = {
        "model": model,
        # `hardened` = bentuk percobaan ULANG produksi (`llm_messages.build_messages`);
        # default = bentuk percobaan PERTAMA (verbatim).
        "messages": build_messages(
            sample.system,
            sample.user,
            attempt=1 if hardened else 0,
            tag="article_title" if sample.kind == "classify" else "article_summary",
        ),
        "temperature": 0,
        "n": 1,
        "max_tokens": sample.max_tokens,
        "timeout": timeout,
    }
    if mode == "json_object":
        kwargs["response_format"] = {"type": "json_object"}

    t0 = time.monotonic()
    try:
        completion = client.chat.completions.create(**kwargs)
    except openai.APITimeoutError:
        return CallResult(sample.name, mode, "timeout", time.monotonic() - t0)
    except openai.APIConnectionError as e:
        return CallResult(
            sample.name, mode, "connection", time.monotonic() - t0, snippet=str(e)[:200]
        )
    except openai.RateLimitError as e:
        return CallResult(
            sample.name, mode, "rate_limit", time.monotonic() - t0, snippet=str(e)[:200]
        )
    except openai.APIStatusError as e:
        return CallResult(
            sample.name, mode, f"http_{e.status_code}", time.monotonic() - t0, snippet=str(e)[:200]
        )
    except (
        Exception
    ) as e:  # SDK/parsing di sisi klien -- tetap dilaporin, jangan matiin seluruh probe
        return CallResult(sample.name, mode, "error", time.monotonic() - t0, snippet=repr(e)[:200])

    latency = time.monotonic() - t0
    choice = completion.choices[0]
    content = choice.message.content
    category, notes = grade(sample, content, choice.finish_reason)
    raw = content if isinstance(content, str) else json.dumps(content)
    return CallResult(
        sample.name,
        mode,
        category,
        latency,
        served_by=getattr(completion, "model", None),
        finish_reason=choice.finish_reason,
        tokens=getattr(getattr(completion, "usage", None), "total_tokens", None),
        notes=notes,
        snippet=(raw or "").strip().replace("\n", " ")[:200],
        raw=raw or "",
    )


# --- agregasi per model ----------------------------------------------------


@dataclass
class ModelReport:
    model: str
    results: list[CallResult] = field(default_factory=list)

    def rate(self, sample: str | None = None, mode: str | None = None) -> float:
        rs = [
            r
            for r in self.results
            if (sample is None or r.sample == sample) and (mode is None or r.mode == mode)
        ]
        return sum(r.ok for r in rs) / len(rs) if rs else 0.0

    @property
    def worst_rate(self) -> float:
        """Kinerja sample TERBURUK -- itu yang nentuin apakah pipeline
        (classify + ttp, semua jenis judul) beneran andal."""
        pairs = {(r.sample, r.mode) for r in self.results}
        return min((self.rate(name, mode) for name, mode in pairs), default=0.0)

    @property
    def verdict(self) -> str:
        if self.results and all(r.ok for r in self.results):
            return "PASS"
        return "USABLE" if self.worst_rate >= 0.8 else "FAIL"

    def confidence_note(self) -> str | None:
        """ "Lolos semua" dari N panggilan BUKAN berarti gak pernah gagal: aturan
        tiga -- 0 gagal dari N panggilan -> dgn keyakinan 95%, laju gagal
        sebenarnya <= ~3/N. 20 panggilan cuma bisa nyingkirin laju gagal
        tinggi (>15%), bukan yang kecil (~5%) kayak yang pernah kejadian di
        gateway dev (Fase 5: 6,5% sisa gagal)."""
        n = len(self.results)
        if n and all(r.ok for r in self.results):
            return (
                f"0 gagal dari {n} panggilan -> dgn keyakinan 95% laju gagal sebenarnya "
                f"<= ~{min(1.0, 3 / n):.0%}. Mau lebih yakin: naikin --runs."
            )
        return None

    def response_format_hint(self) -> str | None:
        """Model gagal HANYA karena `response_format=json_object` (gateway
        nolak/ngabaikan param itu) tapi lolos tanpa dia -- info penting, sebab
        produksi selalu mengirim param itu."""
        by_mode = {
            mode: [r for r in self.results if r.mode == mode] for mode in ("json_object", "plain")
        }
        if not all(by_mode.values()):
            return None
        rate = {m: sum(r.ok for r in rs) / len(rs) for m, rs in by_mode.items()}
        if rate["json_object"] < 0.8 <= rate["plain"]:
            return (
                "lolos TANPA response_format tapi gagal DENGAN dia -- gateway/model ini gak "
                "cocok sama param yang selalu dikirim produksi"
            )
        return None

    @property
    def failure_after_retries(self) -> float:
        return (1 - self.worst_rate) ** PROD_ATTEMPTS

    def served_by(self) -> set[str]:
        return {r.served_by for r in self.results if r.served_by}


def run_model(
    client: OpenAI,
    model: str,
    *,
    runs: int,
    modes: list[str],
    timeout: float,
    sleep_s: float = 0.0,
    on_result: Any = None,
    samples: list[Sample] | None = None,
    hardened: bool = False,
) -> ModelReport:
    report = ModelReport(model)
    for sample in samples if samples is not None else SAMPLES:
        for mode in modes:
            for _ in range(runs):
                result = call_once(client, model, sample, mode, timeout=timeout, hardened=hardened)
                report.results.append(result)
                if on_result:
                    on_result(result)
                if sleep_s:
                    time.sleep(sleep_s)
    return report


# --- output ----------------------------------------------------------------

ICON = {
    "ok": "ok",
    "persona": "PERSONA",
    "truncated": "TERPOTONG",
    "empty": "KOSONG",
    "not_json": "BUKAN-JSON",
    "bad_schema": "SCHEMA",
    "timeout": "TIMEOUT",
    "connection": "KONEKSI",
    "rate_limit": "429",
}


def print_report(report: ModelReport, *, show_fail: int) -> None:
    v = report.verdict
    print(f"\n=== {report.model} ===")
    served = report.served_by()
    # Gateway nyunat awalan provider ("kr/claude-x" -> "claude-x"): itu BUKAN
    # routing ke model lain, cuma beda penulisan nama.
    expected = {report.model, report.model.split("/", 1)[-1]}
    if served and not served <= expected:
        print(
            f"  dijawab oleh model: {', '.join(sorted(served))}"
            "   <- gateway/combo bisa nge-route ke model lain"
        )
    sample_names = list(dict.fromkeys(r.sample for r in report.results))
    for name in sample_names:
        for mode in sorted({r.mode for r in report.results}):
            rs = [r for r in report.results if r.sample == name and r.mode == mode]
            if not rs:
                continue
            marks = " ".join(ICON.get(r.category, r.category) for r in rs)
            lat = statistics.median(r.latency_s for r in rs)
            good = sum(r.ok for r in rs)
            print(f"  {name:20} [{mode:11}] {good}/{len(rs)}  median {lat:5.1f}s   {marks}")
    warns = sorted({n for r in report.results if r.ok for n in r.notes})
    for w in warns[:4]:
        print(f"    ! {w}")
    shown: set[str] = set()
    for r in report.results:
        if not r.ok and r.category not in shown and show_fail:
            shown.add(r.category)
            detail = "; ".join(r.notes) or ""
            print(f"  contoh gagal ({r.category}, finish={r.finish_reason}): {detail}")
            print(f"    -> {(r.snippet or '(kosong)')[:show_fail]}")
    bound = report.confidence_note()
    if bound:
        print(f"  catatan sampel: {bound}")
    hint = report.response_format_hint()
    if hint:
        print(f"  petunjuk: {hint}")
    print(
        f"  VERDICT: {v}  | sample terburuk {report.worst_rate:.0%} per percobaan "
        f"-> peluang gagal setelah {PROD_ATTEMPTS}x percobaan produksi"
        f" ~ {report.failure_after_retries:.1%}"
    )


def print_summary(reports: list[ModelReport]) -> None:
    print("\n" + "=" * 78)
    print(f"{'MODEL':38} {'VERDICT':8} {'terburuk':>9} {'gagal@3x':>9}  {'median':>7}")
    for r in sorted(reports, key=lambda x: (-x.worst_rate, x.model)):
        lat = statistics.median(c.latency_s for c in r.results) if r.results else 0.0
        print(
            f"{r.model[:38]:38} {r.verdict:8} {r.worst_rate:>9.0%} "
            f"{r.failure_after_retries:>9.1%}  {lat:>6.1f}s"
        )
    print(
        "PASS = semua panggilan lolos | USABLE = >=80% per percobaan "
        "(retry produksi menutup sisanya) | FAIL = di bawah itu"
    )


def save_raw(directory: Path, report: ModelReport) -> None:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", report.model)
    out = directory / safe
    out.mkdir(parents=True, exist_ok=True)
    counters: dict[tuple[str, str], int] = {}
    for r in report.results:
        key = (r.sample, r.mode)
        counters[key] = counters.get(key, 0) + 1
        header = (
            f"# category={r.category} finish={r.finish_reason} "
            f"served_by={r.served_by} latency={r.latency_s:.2f}s\n"
        )
        (out / f"{r.sample}.{r.mode}.{counters[key]}.txt").write_text(header + (r.raw or r.snippet))


# --- CLI -------------------------------------------------------------------


def resolve_credentials(url_arg: str | None) -> tuple[str, str]:
    url, key = url_arg or os.environ.get("LLM__URL", ""), os.environ.get("LLM__API_KEY", "")
    if url and key:
        return url, key
    try:
        from cti_core.config import get_settings

        llm = get_settings().llm
        return url or llm.url, key or llm.api_key
    except Exception as e:
        raise SystemExit(
            "Gak nemu kredensial LLM. Set env LLM__URL dan LLM__API_KEY "
            "(atau jalanin dari root repo "
            f"yang punya .env lengkap).\n(detail settings: {type(e).__name__})"
        ) from e


def list_models(client: OpenAI) -> list[str]:
    return sorted(m.id for m in client.models.list().data)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0], formatter_class=argparse.RawTextHelpFormatter
    )
    ap.add_argument("--url", help="base URL OpenAI-compatible (default: LLM__URL / .env)")
    ap.add_argument("--list", action="store_true", help="cuma tampilkan daftar model di gateway")
    ap.add_argument("--model", action="append", default=[], help="model yang dites (boleh diulang)")
    ap.add_argument("--all", action="store_true", help="tes SEMUA model di gateway, satu per satu")
    ap.add_argument("--runs", type=int, default=3, help="ulangan per input per mode (default 3)")
    ap.add_argument("--timeout", type=float, default=90.0, help="detik per panggilan (default 90)")
    ap.add_argument(
        "--response-format",
        choices=["json_object", "none", "both"],
        default="json_object",
        help="json_object = persis produksi (default) | none = tanpa param | both = dua-duanya",
    )
    ap.add_argument(
        "--hardened",
        action="store_true",
        help="pakai bentuk request percobaan ULANG produksi (judul dibungkus tag + pengingat JSON)",
    )
    ap.add_argument("--titles-file", type=Path, help="judul tambahan (satu per baris) buat dites")
    ap.add_argument("--sleep", type=float, default=0.0, help="jeda antar panggilan (detik)")
    ap.add_argument(
        "--show-fail",
        type=int,
        default=200,
        help="panjang cuplikan respons gagal (0 = sembunyikan)",
    )
    ap.add_argument(
        "--save-raw", type=Path, help="simpan respons mentah per panggilan ke direktori ini"
    )
    ap.add_argument("--json-out", type=Path, help="tulis hasil ringkas ke file JSON")
    args = ap.parse_args(argv)

    url, key = resolve_credentials(args.url)
    if not url or not key:
        print("LLM__URL / LLM__API_KEY kosong.", file=sys.stderr)
        return 2
    client = OpenAI(base_url=url, api_key=key, max_retries=0)
    print(f"gateway: {url}   (key: diset, {len(key)} karakter, tidak dicetak)")

    try:
        available = list_models(client)
    except Exception as e:
        available = []
        print(f"(gak bisa ambil daftar model: {type(e).__name__}: {str(e)[:120]})")

    if args.list:
        print(f"{len(available)} model:")
        for m in available:
            print(f"  {m}")
        return 0

    models = available if args.all else args.model
    if not models:
        print(
            "Pilih --model NAMA (boleh berkali-kali), atau --all. Daftar model: --list",
            file=sys.stderr,
        )
        return 2
    unknown = [m for m in models if available and m not in available]
    if unknown:
        print(f"peringatan: model gak ada di daftar gateway: {', '.join(unknown)}")

    modes = {"json_object": ["json_object"], "none": ["plain"], "both": ["json_object", "plain"]}[
        args.response_format
    ]
    samples = SAMPLES + (samples_from_titles(args.titles_file) if args.titles_file else [])
    total = len(models) * len(samples) * len(modes) * args.runs
    print(
        f"{len(models)} model x {len(samples)} input x {len(modes)} mode x "
        f"{args.runs} ulangan = {total} panggilan\n"
    )

    reports: list[ModelReport] = []
    for i, model in enumerate(models, 1):
        print(f"[{i}/{len(models)}] {model} ...", end="", flush=True)
        report = run_model(
            client,
            model,
            runs=args.runs,
            modes=modes,
            timeout=args.timeout,
            sleep_s=args.sleep,
            on_result=lambda r: print("." if r.ok else "x", end="", flush=True),
            samples=samples,
            hardened=args.hardened,
        )
        print()
        print_report(report, show_fail=args.show_fail)
        if args.save_raw:
            save_raw(args.save_raw, report)
        reports.append(report)

    if len(reports) > 1:
        print_summary(reports)
    if args.json_out:
        args.json_out.write_text(
            json.dumps(
                [
                    {
                        "model": r.model,
                        "verdict": r.verdict,
                        "worst_rate": r.worst_rate,
                        "failure_after_retries": r.failure_after_retries,
                        "served_by": sorted(r.served_by()),
                        "calls": [
                            {k: v for k, v in c.__dict__.items() if k != "raw"} for c in r.results
                        ],
                    }
                    for r in reports
                ],
                indent=2,
            )
        )
        print(f"\nhasil ringkas: {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
