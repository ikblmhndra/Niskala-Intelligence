"""Scheduler beat kustom (QA BUG-D2/D7/D8) -- `PersistentScheduler` bawaan
Celery + dua tambahan kecil, dipasang lewat `app.conf.beat_scheduler` di
`celery_app.py` (`beat_main` tetap manggil `app.Beat(...).run()` biasa):

1. HEARTBEAT: tiap tick (paling sering tiap `_HEARTBEAT_EVERY_S`) nulis
   `cti_core.beat_heartbeat.HEARTBEAT_KEY` ke Redis. Ini satu-satunya bukti
   bahwa LOOP scheduler-nya beneran muter (bukan cuma prosesnya hidup --
   thread renew lock di `beat_main` tetap jalan walau loop beat macet).
   Gagal nulis (Redis gangguan) = warning, BUKAN crash: heartbeat itu alat
   observasi, gak boleh jadi alasan beat berhenti nembak jadwal.

2. GAK ADA CATCH-UP BASI: `PersistentScheduler` nyimpen `last_run_at` per
   entri di file shelve (volume `beat-data`). Beat yang mati berhari-hari lalu
   nyala lagi nemu SEMUA entri "due" (slot sesudah `last_run_at` udah lewat)
   dan nembak semuanya sekaligus -- kejadian di staging 2026-09-30 17:17 UTC:
   109 run dalam 7 menit, `any_run_trends` (cron Senin 00:00) jalan Rabu,
   `report-weekly-*` ikut terkirim di hari yang salah. Di sini, entri yang
   slot terakhirnya terlewat lebih lama dari `beat_catchup_grace_s` dilompatin
   ke slot berikutnya; restart singkat (deploy) tetap di-catch-up."""

from __future__ import annotations

import datetime
import time
from collections.abc import Iterable
from typing import Any

import structlog
from celery.beat import PersistentScheduler, ScheduleEntry
from cti_core import beat_heartbeat
from cti_core.config import get_settings

log = structlog.get_logger("cti_worker.scheduler")

_HEARTBEAT_EVERY_S = 15.0


def skip_stale_catchup(
    entries: Iterable[ScheduleEntry], *, now: datetime.datetime, grace_s: float
) -> list[str]:
    """Majuin `last_run_at` ke `now` buat entri yang due HANYA karena slot
    yang udah lama lewat (lebih tua dari `grace_s`). Balikin nama entri yang
    dilompatin. Entri yang punya slot di dalam `(now - grace_s, now]` tetap
    due -- itu catch-up yang sah (beat restart sebentar pas slotnya)."""
    floor = now - datetime.timedelta(seconds=grace_s)
    skipped: list[str] = []
    for entry in entries:
        schedule = entry.schedule
        if not hasattr(schedule, "remaining_estimate"):
            continue
        is_due, _ = entry.is_due()
        if not is_due:
            continue
        base = max(entry.last_run_at, floor)
        # `remaining_estimate(x)` = jarak dari SEKARANG ke slot pertama sesudah
        # `x`. <= 0 berarti ada slot di (base, now] -> masih dalam jendela.
        if schedule.remaining_estimate(base).total_seconds() <= 0:
            continue
        entry.last_run_at = now
        skipped.append(entry.name)
    return skipped


class CtiScheduler(PersistentScheduler):  # type: ignore[misc]  # celery tanpa stub
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._redis: Any = None
        self._started_at = datetime.datetime.now(datetime.UTC)
        self._last_heartbeat = 0.0
        super().__init__(*args, **kwargs)

    def setup_schedule(self) -> None:
        super().setup_schedule()
        grace_s = get_settings().worker.beat_catchup_grace_s
        skipped = skip_stale_catchup(self.schedule.values(), now=self.app.now(), grace_s=grace_s)
        if skipped:
            log.warning(
                "beat_stale_catchup_skipped",
                count=len(skipped),
                grace_s=grace_s,
                entries=sorted(skipped),
            )
            self.sync()

    def tick(self, *args: Any, **kwargs: Any) -> float:
        delay: float = super().tick(*args, **kwargs)
        self._maybe_heartbeat()
        return delay

    def _maybe_heartbeat(self) -> None:
        mono = time.monotonic()
        if mono - self._last_heartbeat < _HEARTBEAT_EVERY_S:
            return
        self._last_heartbeat = mono
        try:
            if self._redis is None:
                import redis

                self._redis = redis.Redis.from_url(get_settings().redis.url)
            now = datetime.datetime.now(datetime.UTC)
            self._redis.set(
                beat_heartbeat.HEARTBEAT_KEY, beat_heartbeat.encode(now, self._started_at)
            )
        except Exception as e:  # observasi doang -- jangan pernah matiin beat
            log.warning("beat_heartbeat_write_failed", error=str(e))
