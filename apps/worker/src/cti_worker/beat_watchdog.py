"""Watchdog heartbeat beat -- jalan di proses WORKER, bukan di beat (QA BUG-D2).

Kenapa gak cukup ditaruh di digest health (`scraper.health_digest`): digest itu
DIJADWALKAN beat. Insiden staging 2026-09-26 15:42 -> 09-30 17:17 UTC: container
`beat` di-stop manual (exit 0, `hasBeenManuallyStopped=true`, jadi `restart:
unless-stopped` memang gak nyalain lagi), digest ikut berhenti, dan "diam"
dibaca sebagai "sehat" selama ~97,6 jam. Worker (`worker`, `worker-browser`,
`worker-nlp`) tetap hidup sepanjang insiden itu -- jadi alarm ditaruh di sana.

Thread daemon di proses INDUK worker (`worker_ready`, bukan tiap child
prefork). Tiga container worker sama-sama ngecek; yang kirim alert cuma satu
per jendela lewat `SET NX EX` di Redis (`_ALERT_KEY`). Pas heartbeat segar
lagi, container yang berhasil `DEL` key itu yang kirim pesan "pulih".
Topic Telegram = `scraper_health` (sama dengan digest) -- operator gak perlu
daftar topic baru di `TELEGRAM__THREAD_IDS`.

Dimatikan di `environment=dev` (laptop: worker sering jalan tanpa beat)."""

from __future__ import annotations

import datetime
import threading
from collections.abc import Callable
from typing import Any

import structlog
from cti_core import beat_heartbeat
from cti_core.config import get_settings

log = structlog.get_logger("cti_worker.beat_watchdog")

_ALERT_KEY = "cti:beat:stale_alerted"
_TOPIC = "scraper_health"

_started = False
_start_lock = threading.Lock()


def _fmt_age(age_s: float | None) -> str:
    if age_s is None:
        return "tidak pernah"
    minutes = int(age_s // 60)
    if minutes < 120:
        return f"{minutes} menit lalu"
    return f"{minutes // 60} jam {minutes % 60} menit lalu"


def check_once(
    client: Any,
    *,
    now: datetime.datetime,
    stale_after_s: int,
    repeat_s: int,
    send: Callable[[str, str], None],
) -> str:
    """Satu putaran cek. Balikin aksi yang diambil (buat log/test):
    `ok` | `stale_alerted` | `stale_suppressed` | `recovered`."""
    status = beat_heartbeat.classify(
        beat_heartbeat.parse(client.get(beat_heartbeat.HEARTBEAT_KEY)),
        now=now,
        stale_after_s=stale_after_s,
    )
    if status.state == "ok":
        if client.delete(_ALERT_KEY):
            send(
                _TOPIC,
                "<b>Scheduler (beat) PULIH</b> -- heartbeat segar lagi "
                f"(tick terakhir {status.last_tick:%Y-%m-%d %H:%M:%S} UTC).",
            )
            log.info("beat_watchdog_recovered")
            return "recovered"
        return "ok"

    if not client.set(_ALERT_KEY, now.isoformat(), nx=True, ex=repeat_s):
        return "stale_suppressed"

    last = f"{status.last_tick:%Y-%m-%d %H:%M:%S} UTC" if status.last_tick else "-"
    send(
        _TOPIC,
        "<b>Scheduler (beat) MATI/MACET</b> -- jadwal scraper & laporan TIDAK jalan.\n"
        f"Heartbeat terakhir: {last} ({_fmt_age(status.age_s)}), ambang {stale_after_s} dtk.\n"
        "Cek: <code>docker compose ps beat</code> / <code>logs beat</code>.",
    )
    log.warning("beat_watchdog_stale", state=status.state, age_s=status.age_s)
    return "stale_alerted"


def _loop(interval_s: int) -> None:
    import redis
    from cti_alerts.telegram import send_alert

    settings = get_settings()
    client = redis.Redis.from_url(settings.redis.url)
    stop = threading.Event()
    while not stop.wait(interval_s):
        try:
            check_once(
                client,
                now=datetime.datetime.now(datetime.UTC),
                stale_after_s=settings.worker.beat_heartbeat_stale_s,
                repeat_s=settings.worker.beat_stale_alert_repeat_min * 60,
                send=send_alert,
            )
        except Exception as e:  # Redis/Telegram gangguan -- coba lagi putaran berikutnya
            log.warning("beat_watchdog_error", error=str(e))


def start() -> bool:
    """Idempoten. `False` kalau gak dinyalain (dev, atau udah jalan)."""
    global _started
    settings = get_settings()
    if settings.environment == "dev":
        return False
    with _start_lock:
        if _started:
            return False
        _started = True
    threading.Thread(
        target=_loop,
        args=(settings.worker.beat_watchdog_interval_s,),
        name="beat-watchdog",
        daemon=True,
    ).start()
    log.info("beat_watchdog_started", interval_s=settings.worker.beat_watchdog_interval_s)
    return True
