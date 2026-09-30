"""`tools/llm/probe_json.py` -- probe kepatuhan-JSON model LLM.

Dites lawan server OpenAI-compatible PALSU yang niru tiap cara model bisa
gagal ngikutin instruksi JSON (termasuk kasus persona "Kiro" di 9router).
Tujuannya: gradernya benar-benar MEMBEDAKAN kegagalan -- kalau semua gagal
dilaporin "gagal" doang, script-nya gak berguna buat milih model.
"""

from __future__ import annotations

import collections
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest
from openai import OpenAI

from tools.llm import probe_json as probe

CYBER = {
    "title": "t",
    "related_cyber": True,
    "confidence": 0.9,
    "reason": "ransomware",
    "industries_impacted": ["Finance & Insurance"],
    "security_tech_best_practice": False,
    "victim_countries": ["Indonesia"],
    "actor_countries": [],
    "confirmed_incident": True,
    "incident_confidence": 0.9,
    "incident_indicators": ["named_victim"],
    "victim_name": "Bank Syariah Indonesia",
}
TTP = {
    "has_techniques": True,
    "techniques": [
        {"technique_name": "Phishing", "technique_id": "T1566.001", "evidence": "spear-phishing"}
    ],
}
KIRO = (
    "Hi! I'm Kiro, an AI assistant for developers. I can't just output raw JSON like that, "
    "but I'd be happy to help you think through the classification!"
)

BEHAVIORS = [
    "good", "fenced", "think", "kiro", "truncated", "empty", "stringbool", "badttp",
    "err500", "nojsonfmt", "flaky", "wrongsem", "alias", "kiro_unless_hardened",
]  # fmt: skip

_calls: collections.Counter[str] = collections.Counter()


def _payload(system: str, user: str, *, cyber: bool | None = None) -> dict[str, Any]:
    if "MITRE ATT&CK" in system:
        return TTP
    is_cyber = ("smartphone" not in user) if cyber is None else cyber
    return {**CYBER, "related_cyber": is_cyber}


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args: Any) -> None:  # diam
        pass

    def _send(self, code: int, obj: dict[str, Any]) -> None:
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        data = [{"id": m, "object": "model"} for m in BEHAVIORS]
        self._send(200, {"object": "list", "data": data})

    def do_POST(self) -> None:
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        model = req["model"]
        system, user = req["messages"][0]["content"], req["messages"][1]["content"]
        _calls[model] += 1
        content: Any = json.dumps(_payload(system, user))
        finish, served = "stop", model

        if model == "fenced":
            content = f"```json\n{content}\n```"
        elif model == "think":
            content = f"<think>hmm, let me reason about this for a while</think>\n{content}"
        elif model == "kiro":
            content = KIRO
        elif model == "truncated":
            content, finish = "<think>Let me think about this step by", "length"
        elif model == "empty":
            content = ""
        elif model == "stringbool":
            p = _payload(system, user)
            p = {**p, "related_cyber": "true"} if "related_cyber" in p else p
            content = json.dumps(p)
        elif model == "badttp":
            if "MITRE ATT&CK" in system:
                content = json.dumps(
                    {"has_techniques": True, "techniques": [{"technique_name": "x"}]}
                )
        elif model == "err500":
            return self._send(500, {"error": {"message": "boom", "type": "server_error"}})
        elif model == "nojsonfmt" and "response_format" in req:
            return self._send(400, {"error": {"message": "response_format not supported"}})
        elif model == "flaky":
            content = KIRO if _calls[model] % 2 == 0 else content
        elif model == "wrongsem":
            content = json.dumps(_payload(system, user, cyber=True))
        elif model == "alias":
            served = "backend-x"
        elif model == "kiro_unless_hardened":
            # persona KECUALI judul dibungkus <article_...> (bentuk retry produksi)
            content = content if user.startswith("<article_") else KIRO

        choice = {
            "index": 0,
            "message": {"role": "assistant", "content": content},
            "finish_reason": finish,
        }
        self._send(
            200,
            {
                "id": "x",
                "object": "chat.completion",
                "created": 0,
                "model": served,
                "choices": [choice],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )


@pytest.fixture(scope="module")
def server_url():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/v1"
    srv.shutdown()


@pytest.fixture
def client(server_url: str) -> OpenAI:
    return OpenAI(base_url=server_url, api_key="k", max_retries=0)


def run(client: OpenAI, model: str, *, runs: int = 2, modes: list[str] | None = None):
    return probe.run_model(client, model, runs=runs, modes=modes or ["json_object"], timeout=10)


def categories(report: probe.ModelReport, sample: str | None = None) -> set[str]:
    return {r.category for r in report.results if sample is None or r.sample == sample}


@pytest.mark.parametrize("model", ["good", "fenced", "think"])
def test_models_that_follow_json_pass_even_with_fences_or_think_blocks(client, model) -> None:
    """Fence ```json dan blok <think> ditoleransi parser produksi -- probe harus
    ikut menganggapnya lolos."""
    report = run(client, model)

    assert categories(report) == {"ok"}
    assert report.verdict == "PASS"


def test_kiro_persona_is_reported_as_persona_not_generic_failure(client) -> None:
    report = run(client, "kiro")

    assert categories(report) == {"persona"}
    assert report.verdict == "FAIL"
    assert "Kiro" in report.results[0].snippet
    assert report.failure_after_retries == 1.0


def test_truncated_and_empty_are_distinguished(client) -> None:
    assert categories(run(client, "truncated")) == {"truncated"}
    assert categories(run(client, "empty")) == {"empty"}


def test_string_boolean_is_a_schema_failure(client) -> None:
    """`bool("false")` di `classify()` = True: model yang ngirim "false" sebagai
    string bakal DIAM-DIAM salah klasifikasi, bukan crash. Harus ketahuan."""
    report = run(client, "stringbool")

    assert categories(report, "classify_cyber") == {"bad_schema"}
    assert any("tipe related_cyber salah" in n for r in report.results for n in r.notes)
    assert categories(report, "ttp") == {"ok"}
    assert report.verdict == "FAIL"


def test_ttp_without_technique_id_would_keyerror_in_production(client) -> None:
    report = run(client, "badttp")

    assert categories(report, "ttp") == {"bad_schema"}
    assert categories(report, "classify_cyber") == {"ok"}


def test_http_errors_carry_their_status(client) -> None:
    assert categories(run(client, "err500")) == {"http_500"}


def test_unsupported_response_format_is_caught_and_plain_mode_shows_the_alternative(
    client,
) -> None:
    report = run(client, "nojsonfmt", modes=["json_object", "plain"])

    assert {r.category for r in report.results if r.mode == "json_object"} == {"http_400"}
    assert {r.category for r in report.results if r.mode == "plain"} == {"ok"}
    assert report.verdict == "FAIL"  # produksi PAKAI json_object
    assert "TANPA response_format" in (report.response_format_hint() or "")


def test_flaky_model_gets_a_realistic_failure_estimate(client) -> None:
    report = run(client, "flaky", runs=2)

    assert 0 < report.worst_rate < 1
    assert report.failure_after_retries == pytest.approx((1 - report.worst_rate) ** 3)


def test_semantic_mismatch_is_a_warning_not_a_json_failure(client) -> None:
    report = run(client, "wrongsem")

    assert report.verdict == "PASS"
    noncyber = [r for r in report.results if r.sample == "classify_noncyber"]
    assert all("semantik: related_cyber=True" in " ".join(r.notes) for r in noncyber)


def test_served_by_exposes_gateway_routing_to_another_model(client) -> None:
    assert run(client, "alias").served_by() == {"backend-x"}


def test_confidence_bool_is_not_accepted_as_a_number() -> None:
    ok, notes = probe.check_schema("classify", {**CYBER, "confidence": True})

    assert not ok and "confidence" in notes[0]


def test_list_all_and_summary_via_cli(
    server_url: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path
) -> None:
    monkeypatch.setenv("LLM__URL", server_url)
    monkeypatch.setenv("LLM__API_KEY", "super-secret-key-123")

    assert probe.main(["--list"]) == 0
    listing = capsys.readouterr().out
    assert "kiro" in listing and "good" in listing
    assert "super-secret-key-123" not in listing  # key gak boleh bocor

    out = tmp_path / "res.json"
    raw = tmp_path / "raw"
    rc = probe.main(
        [
            *("--model", "good", "--model", "kiro", "--runs", "1"),
            *("--json-out", str(out), "--save-raw", str(raw)),
        ]
    )
    text = capsys.readouterr().out

    assert rc == 0
    assert "VERDICT: PASS" in text and "VERDICT: FAIL" in text
    assert "PERSONA" in text and "MODEL" in text  # tabel ringkasan
    assert "super-secret-key-123" not in text
    data = json.loads(out.read_text())
    assert {d["model"]: d["verdict"] for d in data} == {"good": "PASS", "kiro": "FAIL"}
    saved = (raw / "kiro" / "classify_cyber.json_object.1.txt").read_text()
    assert saved.startswith("# category=persona")


def test_missing_selection_is_a_usage_error(
    server_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLM__URL", server_url)
    monkeypatch.setenv("LLM__API_KEY", "k")

    assert probe.main([]) == 2


def _report(model: str, served: str | None, n: int = 4) -> probe.ModelReport:
    rep = probe.ModelReport(model)
    rep.results = [
        probe.CallResult("classify_cyber", "json_object", "ok", 1.0, served_by=served)
        for _ in range(n)
    ]
    return rep


def test_provider_prefix_difference_is_not_reported_as_routing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    probe.print_report(_report("kr/claude-sonnet-4.5", "claude-sonnet-4.5"), show_fail=0)
    assert "dijawab oleh model" not in capsys.readouterr().out

    probe.print_report(_report("my-combo", "claude-haiku-4.5"), show_fail=0)
    assert "dijawab oleh model: claude-haiku-4.5" in capsys.readouterr().out


def test_all_pass_reports_the_statistical_ceiling_not_just_100_percent(
    capsys: pytest.CaptureFixture[str],
) -> None:
    probe.print_report(_report("m", None, n=20), show_fail=0)
    out = capsys.readouterr().out

    assert "0 gagal dari 20 panggilan" in out and "<= ~15%" in out


def test_hardened_shape_rescues_a_model_that_only_fails_the_plain_shape(client) -> None:
    """Persis pola gateway dev: bentuk verbatim dijawab persona, bentuk retry
    yang dikuatkan lolos. Probe harus nunjukkin BEDANYA."""
    plain = run(client, "kiro_unless_hardened")
    hardened = probe.run_model(
        client, "kiro_unless_hardened", runs=2, modes=["json_object"], timeout=10, hardened=True
    )

    assert categories(plain) == {"persona"} and plain.verdict == "FAIL"
    assert categories(hardened) == {"ok"} and hardened.verdict == "PASS"


def test_known_kiro_titles_are_built_in_samples() -> None:
    names = {s.name for s in probe.SAMPLES}

    assert {"classify_kiro_1", "classify_kiro_2"} <= names


def test_titles_file_adds_custom_samples(client, tmp_path) -> None:
    f = tmp_path / "titles.txt"
    f.write_text("Judul satu\n\n  Judul dua  \n")

    samples = probe.samples_from_titles(f)
    report = probe.run_model(
        client, "good", runs=1, modes=["json_object"], timeout=10, samples=samples
    )

    assert [s.user for s in samples] == ["Judul satu", "Judul dua"]
    assert {r.sample for r in report.results} == {"custom_1", "custom_2"}
    assert report.verdict == "PASS"
