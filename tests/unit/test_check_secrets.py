"""`tools/ops/check_secrets.py` -- verifikasi key ke provider (read-only).

Semua HTTP di-mock (respx). Yang dikunci: statusnya bener, exit code bener,
dan -- paling penting -- SECRET TIDAK PERNAH BOCOR ke output, termasuk lewat
pesan error httpx yang memuat URL (Telegram naruh token di path URL).
"""

from __future__ import annotations

import httpx
import respx
from cti_core.config import (
    GithubSettings,
    GraphSettings,
    LlmSettings,
    NvdSettings,
    Settings,
    TelegramSettings,
    TwitterSettings,
    XSettings,
)  # fmt: skip

from tools.ops import check_secrets as cs

# Secret PALSU (bukan key beneran) -- `gitleaks:allow` biar gate CI gak nangkep.
LLM_KEY = "sk-llm-SECRET-123456"  # gitleaks:allow
TG_TOKEN = "111222333:TG-SECRET-TOKEN-abcdef"  # gitleaks:allow
NVD_KEY = "nvd-SECRET-key-987654"  # gitleaks:allow
GH_TOKEN = "ghp_SECRETSECRETSECRET1234"  # gitleaks:allow
TW_KEY = "tw-SECRET-key-555555"  # gitleaks:allow
X_BEARER = "AAAA-x-SECRET-bearer-777777"  # gitleaks:allow


def make_settings(**over: object) -> Settings:
    base = {
        "database": {"url": "postgresql+asyncpg://x:x@h/x", "sync_url": "postgresql+psycopg://x:x@h/x"},
        "auth": {"jwt_secret": "j", "session_secret_key": "s"},
        "llm": LlmSettings(url="http://gw:20128/v1", api_key=LLM_KEY, model="my-combo"),
        "telegram": TelegramSettings(bot_token=TG_TOKEN, chat_id="-100123"),
        "nvd": NvdSettings(api_key=NVD_KEY),
        "github": GithubSettings(token=GH_TOKEN),
        "twitter": TwitterSettings(api_key=TW_KEY),
        "x": XSettings(bearer_token=X_BEARER),
    }  # fmt: skip
    return Settings(**{**base, **over})


def mock_all_ok(mock: respx.MockRouter) -> None:
    mock.get("http://gw:20128/v1/models").respond(
        json={"object": "list", "data": [{"id": "my-combo", "object": "model"}]}
    )
    mock.get(url__regex=r"https://api\.telegram\.org/bot.*/getMe").respond(
        json={"ok": True, "result": {"username": "stg_bot"}}
    )
    mock.get(url__regex=r"https://api\.telegram\.org/bot.*/getChat.*").respond(
        json={"ok": True, "result": {"title": "CTI Test", "is_forum": True}}
    )
    mock.get(url__regex=r"https://services\.nvd\.nist\.gov/.*").respond(json={})
    mock.get("https://api.github.com/rate_limit").respond(
        json={"resources": {"core": {"limit": 5000, "remaining": 4990}}}
    )
    mock.get(url__regex=r"https://api\.twitterapi\.io/.*").respond(json={})
    mock.get("https://api.x.com/2/usage/tweets").respond(
        json={"data": {"project_usage": "5551", "project_cap": "3000000"}}
    )


@respx.mock
def test_all_valid_keys_report_ok_and_exit_zero() -> None:
    mock_all_ok(respx.mock)

    results = cs.run_checks(make_settings())

    assert {r.name: r.status for r in results} == {
        "llm": "OK",
        "telegram": "OK",
        "nvd": "OK",
        "github": "OK",
        "twitter": "OK",
        "x": "OK",
        "graph": "SKIP",
    }
    assert cs.exit_code(results) == 0
    detail = {r.name: r.detail for r in results}
    assert "@stg_bot" in detail["telegram"] and "CTI Test" in detail["telegram"]
    assert "limit 5000" in detail["github"] and "terotentikasi" in detail["github"]


@respx.mock
def test_rejected_optional_key_is_a_failure_but_empty_optional_key_is_only_skip() -> None:
    mock_all_ok(respx.mock)
    respx.mock.get(url__regex=r"https://services\.nvd\.nist\.gov/.*").respond(404)

    results = {r.name: r for r in cs.run_checks(make_settings(github=GithubSettings(token="")))}

    assert results["nvd"].status == "FAIL" and "404" in results["nvd"].detail
    assert results["github"].status == "SKIP"
    assert cs.exit_code(list(results.values())) == 1


@respx.mock
def test_github_token_ignored_is_called_out() -> None:
    mock_all_ok(respx.mock)
    respx.mock.get("https://api.github.com/rate_limit").respond(
        json={"resources": {"core": {"limit": 60, "remaining": 59}}}
    )

    res = {r.name: r for r in cs.run_checks(make_settings())}["github"]

    assert "DIABAIKAN" in res.detail


@respx.mock
def test_bot_valid_but_chat_unreachable_is_explained() -> None:
    mock_all_ok(respx.mock)
    respx.mock.get(url__regex=r"https://api\.telegram\.org/bot.*/getChat.*").respond(
        400, json={"ok": False}
    )

    res = {r.name: r for r in cs.run_checks(make_settings())}["telegram"]

    assert res.status == "FAIL" and "@stg_bot" in res.detail and "-100123" in res.detail


@respx.mock
def test_llm_model_missing_from_gateway_list_fails() -> None:
    mock_all_ok(respx.mock)
    respx.mock.get("http://gw:20128/v1/models").respond(
        json={"object": "list", "data": [{"id": "lain", "object": "model"}]}
    )

    res = {r.name: r for r in cs.run_checks(make_settings())}["llm"]

    assert res.status == "FAIL" and "my-combo" in res.detail


@respx.mock
def test_secrets_never_leak_even_when_the_error_message_contains_the_url() -> None:
    """httpx error untuk Telegram memuat URL (token di path). Output cuma boleh
    nampilin TIPE error, dan `redact` jadi jaring pengaman terakhir."""
    mock_all_ok(respx.mock)
    respx.mock.get(url__regex=r"https://api\.telegram\.org/bot.*/getMe").mock(
        side_effect=httpx.ConnectError(f"boom https://api.telegram.org/bot{TG_TOKEN}/getMe")
    )

    results = cs.run_checks(make_settings())
    output = " ".join(f"{r.name} {r.status} {r.detail}" for r in results)

    assert {r.name: r.status for r in results}["telegram"] == "FAIL"
    for secret in (LLM_KEY, TG_TOKEN, NVD_KEY, GH_TOKEN, TW_KEY, X_BEARER):
        assert secret not in output
    assert "ConnectError" in output


def test_graph_filled_is_a_note_never_called() -> None:
    settings = make_settings(
        graph=GraphSettings(
            tenant_id="t", client_id="c", client_secret="s3cr3t-value", sender="a@b.c"
        )
    )

    res = {r.name: r for r in cs.run_checks(settings, only=["graph"])}["graph"]

    assert res.status == "NOTE" and "BENERAN" in res.detail and "s3cr3t-value" not in res.detail


@respx.mock
def test_only_flag_runs_just_the_selected_checks() -> None:
    mock_all_ok(respx.mock)

    results = cs.run_checks(make_settings(), only=["llm", "nvd"])

    assert [r.name for r in results] == ["llm", "nvd"]


@respx.mock
def test_x_bearer_is_validated_via_the_usage_endpoint_with_a_bearer_header() -> None:
    """`/2/usage/tweets` = pemakaian, bukan baca tweet: memvalidasi bearer tanpa tagihan baca."""
    mock_all_ok(respx.mock)

    res = {r.name: r for r in cs.run_checks(make_settings(), only=["x"])}["x"]

    call = next(c for c in respx.mock.calls if c.request.url.host == "api.x.com")
    assert call.request.headers["authorization"] == f"Bearer {X_BEARER}"
    assert res.status == "OK" and "5551/3000000" in res.detail and X_BEARER not in res.detail


@respx.mock
def test_x_bearer_rejected_is_a_failure_and_empty_is_a_skip_because_it_is_only_the_backup() -> None:
    mock_all_ok(respx.mock)
    respx.mock.get("https://api.x.com/2/usage/tweets").respond(401, json={"title": "Unauthorized"})

    rejected = {r.name: r for r in cs.run_checks(make_settings(), only=["x"])}["x"]
    empty = {
        r.name: r for r in cs.run_checks(make_settings(x=XSettings(bearer_token="")), only=["x"])
    }["x"]

    assert rejected.status == "FAIL" and "401" in rejected.detail
    assert empty.status == "SKIP"
    assert cs.exit_code([rejected]) == 1 and cs.exit_code([empty]) == 0


@respx.mock
def test_the_x_bearer_is_redacted_even_if_a_response_echoes_it_back() -> None:
    """Jaring pengaman terakhir: kalau provider (atau proxy) memantulkan bearer di badan respons,
    `redact` tetap menutupnya sebelum sampai ke output."""
    mock_all_ok(respx.mock)
    respx.mock.get("https://api.x.com/2/usage/tweets").respond(
        json={"data": {"project_usage": X_BEARER, "project_cap": "3000000"}}
    )

    res = {r.name: r for r in cs.run_checks(make_settings(), only=["x"])}["x"]

    assert X_BEARER not in res.detail and "***" in res.detail
