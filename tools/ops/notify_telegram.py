#!/usr/bin/env python3
"""Kirim satu pesan teks ke topik Telegram platform dari cron/systemd (Fase 10.G). Cuma stdlib,
tanpa `uv sync`: dipakai `pg_backup.py --on-failure-cmd`, atau skrip operasi lain di HOST
yang butuh mengabari kalau ada yang gagal (backup, prune disk, dst).

    python3 tools/ops/notify_telegram.py --env-file .env --topic debug --text "BACKUP GAGAL: ..."

Membaca `TELEGRAM__BOT_TOKEN`, `TELEGRAM__CHAT_ID`, dan `TELEGRAM__THREAD_IDS` (JSON) LANGSUNG
dari berkas env (tanpa di-source: nilai JSON dan karakter aneh tidak dieksekusi shell). Token
TIDAK pernah dicetak -- juga tidak lewat pesan error. Teks polos (tanpa parse_mode), dipotong ke
batas 4096 karakter Telegram.

Topik yang tidak ada di `TELEGRAM__THREAD_IDS` = GAGAL keras (exit 1), bukan diam-diam terkirim
ke channel utama -- sama seperti `cti_alerts.telegram`. Thread 0 = channel utama tanpa thread.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Sequence
from pathlib import Path

TEXT_LIMIT = 4096
API = "https://api.telegram.org/bot{token}/sendMessage"


class NotifyError(Exception):
    pass


def read_env(path: Path) -> dict[str, str]:
    """`KEY=VALUE` per baris; komentar dan baris kosong dilewati; kutip pembungkus dibuang.
    Tidak ada ekspansi variabel dan tidak ada eksekusi."""
    values: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if value[:1] in "\"'" and value[-1:] == value[:1] and len(value) >= 2:
            value = value[1:-1]
        elif " #" in value:  # komentar di ujung baris (`KEY=nilai   # catatan`)
            value = value.split(" #", 1)[0].rstrip()
        values[key.strip()] = value
    return values


def build_request(env: dict[str, str], topic: str, text: str) -> tuple[str, dict[str, str]]:
    token = env.get("TELEGRAM__BOT_TOKEN", "")
    chat = env.get("TELEGRAM__CHAT_ID", "")
    if not token or not chat:
        raise NotifyError("TELEGRAM__BOT_TOKEN/TELEGRAM__CHAT_ID kosong di berkas env")
    try:
        threads = json.loads(env.get("TELEGRAM__THREAD_IDS") or "{}")
    except ValueError as e:
        raise NotifyError(f"TELEGRAM__THREAD_IDS bukan JSON valid: {e}") from e
    if topic not in threads:
        raise NotifyError(
            f"topik '{topic}' tidak ada di TELEGRAM__THREAD_IDS (ada: {sorted(threads)})"
        )

    params = {"chat_id": chat, "text": text[:TEXT_LIMIT], "disable_web_page_preview": "true"}
    if int(threads[topic]):
        params["message_thread_id"] = str(int(threads[topic]))
    return API.format(token=token), params


def send(
    env: dict[str, str],
    topic: str,
    text: str,
    *,
    opener: Callable[..., object] = urllib.request.urlopen,
) -> None:
    url, params = build_request(env, topic, text)
    request = urllib.request.Request(
        url, data=urllib.parse.urlencode(params).encode(), method="POST"
    )
    try:
        opener(request, timeout=20)  # type: ignore[operator]
    except urllib.error.HTTPError as e:
        raise NotifyError(f"Telegram menolak: HTTP {e.code}") from None  # tanpa URL (memuat token)
    except (urllib.error.URLError, OSError) as e:
        raise NotifyError(f"Telegram tak terjangkau: {type(e).__name__}") from None


def main(argv: Sequence[str] | None = None, *, opener: Callable[..., object] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--topic", default="debug")
    parser.add_argument("--text", required=True)
    args = parser.parse_args(argv)
    try:
        send(
            read_env(args.env_file), args.topic, args.text, opener=opener or urllib.request.urlopen
        )
    except (NotifyError, OSError) as e:
        print(f"GAGAL: {e}", file=sys.stderr)
        return 1
    print(f"OK: terkirim ke topik '{args.topic}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
