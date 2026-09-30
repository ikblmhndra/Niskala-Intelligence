"""`tools/ops/notify_telegram.py` -- pesan dari cron/systemd ke topik Telegram (Fase 10.G)."""

from __future__ import annotations

import urllib.error
import urllib.parse
from pathlib import Path

import pytest

from tools.ops import notify_telegram as nt

TOKEN = "123456:SECRET-TOKEN-VALUE"
ENV_TEXT = f"""# komentar
# TELEGRAM__CHAT_ID=-999 (dinonaktifkan)
TELEGRAM__BOT_TOKEN={TOKEN}
TELEGRAM__CHAT_ID=-1001234
TELEGRAM__THREAD_IDS={{"debug": 42, "global": 0, "pir": 7}}   # topik
OTHER="dikutip"
  SPACED = nilai  
"""


@pytest.fixture
def env(tmp_path: Path) -> dict[str, str]:
    path = tmp_path / ".env"
    path.write_text(ENV_TEXT)
    return nt.read_env(path)


class Opener:
    def __init__(self, error: Exception | None = None) -> None:
        self.error, self.requests = error, []

    def __call__(self, request, timeout=None):
        self.requests.append(request)
        if self.error:
            raise self.error
        return object()


def body(request) -> dict[str, str]:
    return dict(urllib.parse.parse_qsl(request.data.decode()))


def test_env_parsing_skips_comments_strips_quotes_and_inline_comments_without_executing_anything(
    env: dict[str, str],
) -> None:
    assert env["TELEGRAM__BOT_TOKEN"] == TOKEN
    assert (
        env["TELEGRAM__THREAD_IDS"] == '{"debug": 42, "global": 0, "pir": 7}'
    )  # komentar ujung dibuang
    assert env["OTHER"] == "dikutip" and env["SPACED"] == "nilai"
    assert not [k for k in env if k.startswith("#")]  # baris yang dikomentari tidak ikut terbaca
    assert env["TELEGRAM__CHAT_ID"] == "-1001234"


def test_the_message_goes_to_the_topics_thread(env: dict[str, str]) -> None:
    opener = Opener()

    nt.send(env, "debug", "backup gagal", opener=opener)

    [request] = opener.requests
    assert request.full_url == f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    assert body(request) == {
        "chat_id": "-1001234",
        "text": "backup gagal",
        "disable_web_page_preview": "true",
        "message_thread_id": "42",
    }


def test_thread_zero_means_the_main_channel_without_a_thread_id(env: dict[str, str]) -> None:
    opener = Opener()

    nt.send(env, "global", "halo", opener=opener)

    assert "message_thread_id" not in body(opener.requests[0])


def test_an_unknown_topic_fails_loudly_instead_of_posting_to_the_main_channel(
    env: dict[str, str],
) -> None:
    opener = Opener()

    with pytest.raises(nt.NotifyError, match=r"topik 'nope' tidak ada.*debug"):
        nt.send(env, "nope", "x", opener=opener)

    assert opener.requests == []


@pytest.mark.parametrize("missing", ["TELEGRAM__BOT_TOKEN", "TELEGRAM__CHAT_ID"])
def test_missing_credentials_fail_before_any_request(env: dict[str, str], missing: str) -> None:
    env[missing] = ""
    opener = Opener()

    with pytest.raises(nt.NotifyError, match="kosong"):
        nt.send(env, "debug", "x", opener=opener)

    assert opener.requests == []


def test_broken_thread_json_is_reported(env: dict[str, str]) -> None:
    env["TELEGRAM__THREAD_IDS"] = "{bukan json"

    with pytest.raises(nt.NotifyError, match="bukan JSON valid"):
        nt.build_request(env, "debug", "x")


def test_long_text_is_cut_to_the_telegram_limit(env: dict[str, str]) -> None:
    opener = Opener()

    nt.send(env, "debug", "x" * 10_000, opener=opener)

    assert len(body(opener.requests[0])["text"]) == nt.TEXT_LIMIT


def test_errors_never_leak_the_token(env: dict[str, str]) -> None:
    http = urllib.error.HTTPError(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage", 401, "no", {}, None
    )  # type: ignore[arg-type]
    net = urllib.error.URLError(f"gagal konek ke bot{TOKEN}")

    for error in (http, net):
        with pytest.raises(nt.NotifyError) as info:
            nt.send(env, "debug", "x", opener=Opener(error))
        assert TOKEN not in str(info.value) and "SECRET" not in str(info.value)
    with pytest.raises(nt.NotifyError, match="HTTP 401"):
        nt.send(env, "debug", "x", opener=Opener(http))


def test_cli_exit_codes_and_no_token_in_output(tmp_path: Path, capsys) -> None:
    path = tmp_path / ".env"
    path.write_text(ENV_TEXT)

    assert (
        nt.main(["--env-file", str(path), "--topic", "debug", "--text", "hi"], opener=Opener()) == 0
    )
    assert "OK" in capsys.readouterr().out

    rc = nt.main(["--env-file", str(path), "--topic", "nope", "--text", "hi"], opener=Opener())
    captured = capsys.readouterr()
    assert rc == 1 and "GAGAL" in captured.err and TOKEN not in captured.err + captured.out

    assert (
        nt.main(["--env-file", str(tmp_path / "tidak-ada"), "--text", "hi"], opener=Opener()) == 1
    )
