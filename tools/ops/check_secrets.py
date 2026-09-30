#!/usr/bin/env python3
"""Cek apakah secret/API key yang dikonfigurasi BENERAN diterima provider-nya
(bukan cuma "terisi"): satu request BACA-DOANG per provider, tanpa efek samping,
tanpa nge-print secret.

Dipakai: verifikasi staging sebelum rehearsal (Fase 10.G), dan verifikasi
SESUDAH rotasi secret di produksi (Fase 10.F) -- key baru yang salah ketik
ketahuan sebelum go-live, bukan pas scraper pertama gagal jam 3 pagi.

    # dari root repo (baca .env), atau di dalam container (baca env-nya):
    uv run python tools/ops/check_secrets.py
    docker run --rm --env-file stg.env -v "$PWD/tools:/tools:ro" cti-worker:stg \\
        python /tools/ops/check_secrets.py

Yang dicek (read-only): LLM `GET /models` (tanpa generate, gak makan kuota),
Telegram `getMe` + `getChat` (TIDAK ngirim pesan), NVD `resultsPerPage=1`,
GitHub `/rate_limit`, twitterapi.io `user/info`, API resmi X `GET /2/usage/tweets` (bearer;
endpoint pemakaian, tidak membaca satu tweet pun -- terverifikasi HTTP 200, tanpa tagihan baca).
Microsoft Graph SENGAJA gak dites (cuma dilaporin terisi atau nggak) -- satu-satunya cara ngetes
adalah ngirim/bikin email beneran.

Exit code 1 kalau ada key yang TERISI tapi DITOLAK, atau LLM/Telegram gagal.
Key opsional yang kosong = SKIP (bukan gagal).
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from typing import Any

import httpx
from cti_core.llm.client import _DEFAULT_BASE_URLS

REQUIRED = {"llm", "telegram"}


@dataclass
class Result:
    name: str
    status: str  # OK | FAIL | SKIP | NOTE
    detail: str = ""


def _secrets(settings: Any) -> list[str]:
    vals = [
        settings.llm.api_key,
        settings.telegram.bot_token,
        settings.nvd.api_key,
        settings.github.token,
        settings.twitter.api_key,
        settings.x.bearer_token,
        settings.graph.client_secret,
    ]
    return [v for v in vals if v and len(v) >= 6]


def redact(text: str, secrets: list[str]) -> str:
    for s in secrets:
        text = text.replace(s, "***")
    return text


def _http_check(
    url: str, *, headers: dict[str, str] | None = None, timeout: float
) -> tuple[httpx.Response | None, str]:
    try:
        return httpx.get(url, headers=headers, timeout=timeout), ""
    except httpx.HTTPError as e:
        # `str(e)` bisa memuat URL (Telegram: token ada di path) -- cuma tipenya.
        return None, type(e).__name__


def check_llm(settings: Any, timeout: float) -> Result:
    llm = settings.llm
    if not llm.api_key:
        return Result("llm", "FAIL", "LLM__API_KEY kosong")
    base = llm.url or _DEFAULT_BASE_URLS.get(llm.provider.lower()) or "https://api.openai.com/v1"
    r, err = _http_check(
        f"{base.rstrip('/')}/models",
        headers={"Authorization": f"Bearer {llm.api_key}"},
        timeout=timeout,
    )
    if r is None:
        return Result("llm", "FAIL", f"{base}: {err}")
    if r.status_code != 200:
        return Result("llm", "FAIL", f"{base}: ditolak (HTTP {r.status_code}) -- key salah/dicabut")
    try:
        models = sorted(m["id"] for m in r.json()["data"])
    except (ValueError, KeyError, TypeError):
        return Result("llm", "FAIL", f"{base}: respons /models bukan format OpenAI")
    if llm.model and models and llm.model not in models:
        return Result(
            "llm", "FAIL", f"{base}: model '{llm.model}' gak ada di daftar ({len(models)} model)"
        )
    return Result("llm", "OK", f"{base} | {len(models)} model | model '{llm.model}' ada")


def check_telegram(settings: Any, timeout: float) -> Result:
    tg = settings.telegram
    if not tg.bot_token or not tg.chat_id:
        return Result("telegram", "FAIL", "BOT_TOKEN / CHAT_ID kosong")
    base = f"https://api.telegram.org/bot{tg.bot_token}"
    r, err = _http_check(f"{base}/getMe", timeout=timeout)
    if r is None:
        return Result("telegram", "FAIL", f"getMe: {err}")
    if r.status_code != 200 or not r.json().get("ok"):
        return Result(
            "telegram", "FAIL", f"getMe ditolak (HTTP {r.status_code}) -- token salah/dicabut"
        )
    bot = r.json()["result"].get("username", "?")
    r, err = _http_check(f"{base}/getChat?chat_id={tg.chat_id}", timeout=timeout)
    if r is None:
        return Result("telegram", "FAIL", f"bot @{bot} valid, getChat: {err}")
    if r.status_code != 200 or not r.json().get("ok"):
        return Result(
            "telegram",
            "FAIL",
            f"bot @{bot} valid, TAPI chat {tg.chat_id} gak bisa diakses "
            f"(HTTP {r.status_code}) -- bot belum masuk chat itu / chat_id salah",
        )
    chat = r.json()["result"]
    forum = "forum (pakai thread)" if chat.get("is_forum") else "chat biasa"
    return Result(
        "telegram", "OK", f"bot @{bot} | chat '{chat.get('title') or chat.get('type')}' ({forum})"
    )


def _optional(
    name: str, key: str, url: str, header: dict[str, str], ok_note: Any, timeout: float
) -> Result:
    if not key:
        return Result(name, "SKIP", "kosong (opsional)")
    r, err = _http_check(url, headers=header, timeout=timeout)
    if r is None:
        return Result(name, "FAIL", err)
    if r.status_code == 200:
        return Result(name, "OK", ok_note(r))
    return Result(name, "FAIL", f"ditolak (HTTP {r.status_code}) -- key salah/dicabut/kuota")


def check_nvd(settings: Any, timeout: float) -> Result:
    return _optional(
        "nvd", settings.nvd.api_key,
        "https://services.nvd.nist.gov/rest/json/cves/2.0?resultsPerPage=1",
        {"apiKey": settings.nvd.api_key}, lambda r: "diterima", timeout,
    )  # fmt: skip


def check_github(settings: Any, timeout: float) -> Result:
    def note(r: httpx.Response) -> str:
        core = r.json().get("resources", {}).get("core", {})
        limit = core.get("limit")
        auth = (
            "terotentikasi" if limit and limit > 60 else "TOKEN DIABAIKAN (limit 60/jam = anonim)"
        )
        return f"{auth} | limit {limit}/jam, sisa {core.get('remaining')}"

    return _optional(
        "github", settings.github.token, "https://api.github.com/rate_limit",
        {"Authorization": f"Bearer {settings.github.token}"}, note, timeout,
    )  # fmt: skip


def check_twitter(settings: Any, timeout: float) -> Result:
    return _optional(
        "twitter", settings.twitter.api_key,
        "https://api.twitterapi.io/twitter/user/info?userName=twitter",
        {"X-API-Key": settings.twitter.api_key}, lambda r: "twitterapi.io menerima key", timeout,
    )  # fmt: skip


def check_x(settings: Any, timeout: float) -> Result:
    """Bearer API resmi X (sumber Twitter CADANGAN). `/2/usage/tweets` = endpoint pemakaian:
    memvalidasi bearer TANPA membaca tweet (jadi tidak ditagih). Kosong = SKIP: cadangan boleh
    belum disiapkan."""

    def note(r: httpx.Response) -> str:
        data = r.json().get("data", {})
        used, cap = data.get("project_usage"), data.get("project_cap")
        return f"X menerima bearer | pemakaian proyek {used}/{cap}"

    return _optional(
        "x", settings.x.bearer_token, "https://api.x.com/2/usage/tweets",
        {"Authorization": f"Bearer {settings.x.bearer_token}"}, note, timeout,
    )  # fmt: skip


def check_graph(settings: Any, timeout: float) -> Result:
    g = settings.graph
    set_fields = [k for k in ("tenant_id", "client_id", "client_secret", "sender") if getattr(g, k)]
    if not set_fields:
        return Result("graph", "SKIP", "kosong")
    return Result(
        "graph",
        "NOTE",
        f"TERISI ({', '.join(set_fields)}) -- gak dites; "
        "di staging ini bisa bikin draft/email BENERAN",
    )


CHECKS = {
    "llm": check_llm,
    "telegram": check_telegram,
    "nvd": check_nvd,
    "github": check_github,
    "twitter": check_twitter,
    "x": check_x,
    "graph": check_graph,
}


def run_checks(
    settings: Any, *, only: list[str] | None = None, timeout: float = 15.0
) -> list[Result]:
    secrets = _secrets(settings)
    results = []
    for name, fn in CHECKS.items():
        if only and name not in only:
            continue
        res = fn(settings, timeout)
        res.detail = redact(res.detail, secrets)
        results.append(res)
    return results


def exit_code(results: list[Result]) -> int:
    return 1 if any(r.status == "FAIL" for r in results) else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--only", help=f"koma-pisah dari: {', '.join(CHECKS)}")
    ap.add_argument("--timeout", type=float, default=15.0)
    args = ap.parse_args(argv)

    from cti_core.config import get_settings

    only = [x.strip() for x in args.only.split(",")] if args.only else None
    results = run_checks(get_settings(), only=only, timeout=args.timeout)
    for r in results:
        req = " (wajib)" if r.name in REQUIRED else ""
        print(f"{r.status:5} {r.name:9}{req:9} {r.detail}")
    code = exit_code(results)
    print(
        "\nSEMUA OK" if code == 0 else "\nADA YANG GAGAL", file=sys.stderr if code else sys.stdout
    )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
