"""Entrypoint beat dengan lock singleton (Fase 10.1d) -- GANTI
`celery -A cti_worker.celery_app beat` di Compose:

    python -m cti_worker.beat_main

Alurnya:
  1. STANDBY: loop `BeatLock.acquire()` sampai berhasil. Selama ini Celery
     beat BELUM dijalanin sama sekali (gak ada tick, gak ada fire).
  2. LEADER: thread latar memperpanjang lock tiap `ttl/3` detik. Kalau
     perpanjangan ditolak (lock bukan punya kita lagi) ATAU Redis gak bisa
     dijangkau lebih lama dari sisa TTL, proses `os._exit(1)` -- FAIL-STOP:
     dua leader jauh lebih parah daripada nol leader beberapa detik, dan
     restart policy Compose yang bawa proses ini balik ke STANDBY.
  3. Celery beat jalan biasa di thread utama. Keluar bersih (SIGTERM) =
     lock dilepas, standby ambil alih seketika, bukan nunggu TTL abis.

Batasan yang diterima: proses leader yang MEMBEKU lebih lama dari TTL
(VM di-pause, swap parah) bisa sempat nge-tick sekali sebelum thread
perpanjangannya sadar lock-nya hilang. TTL default 30 detik; itu risiko
yang sama dengan semua lock berbasis TTL, bukan sesuatu yang bisa dihapus
tanpa fencing token di sisi broker."""

from __future__ import annotations

import os
import threading
import time

import redis
import structlog
from cti_core.config import get_settings
from cti_core.logging import configure_logging

from cti_worker.beat_lock import BeatLock

log = structlog.get_logger("cti_worker.beat_main")


def _renew_loop(lock: BeatLock, *, ttl_s: float, stop: threading.Event) -> None:
    interval = ttl_s / 3
    last_ok = time.monotonic()
    while not stop.wait(interval):
        try:
            if not lock.renew():
                log.critical("beat_lock_lost", reason="renew_rejected")
                os._exit(1)
            last_ok = time.monotonic()
        except redis.RedisError as e:
            # Redis lagi gangguan -- toleransi selama lock kita MASIH
            # mungkin hidup (sisa TTL dari perpanjangan terakhir yang
            # berhasil). Lewat itu, anggap hilang.
            silent_s = time.monotonic() - last_ok
            log.warning("beat_lock_renew_error", error=str(e), silent_s=round(silent_s, 1))
            if silent_s >= ttl_s:
                log.critical("beat_lock_lost", reason="redis_unreachable", silent_s=silent_s)
                os._exit(1)


def main() -> None:
    settings = get_settings()
    configure_logging(level=settings.log_level, json=settings.environment != "dev")

    ttl_s = settings.worker.beat_lock_ttl_s
    client = redis.Redis.from_url(settings.redis.url)
    lock = BeatLock(client, ttl_ms=ttl_s * 1000)

    retry_s = max(1.0, ttl_s / 3)
    waited = 0
    while True:
        try:
            if lock.acquire():
                break
        except redis.RedisError as e:
            log.warning("beat_lock_redis_error", error=str(e))
        if waited % 10 == 0:  # jangan spam log standby tiap detik
            log.info("beat_standby", token=lock.token, retry_s=retry_s)
        waited += 1
        time.sleep(retry_s)

    log.info("beat_leader", token=lock.token, ttl_s=ttl_s)
    stop = threading.Event()
    threading.Thread(
        target=_renew_loop,
        kwargs={"lock": lock, "ttl_s": float(ttl_s), "stop": stop},
        name="beat-lock-renew",
        daemon=True,
    ).start()

    try:
        # Import DI SINI, bukan top-level: `celery_app` bangun beat schedule
        # (`build_beat_schedule()`, query DB) waktu di-import -- standby
        # gak perlu (dan gak boleh gagal gara-gara) itu.
        from cti_worker.celery_app import app

        app.Beat(loglevel=settings.log_level).run()
    finally:
        stop.set()
        lock.release()
        log.info("beat_lock_released", token=lock.token)


if __name__ == "__main__":
    main()
