"""Heartbeat scheduler (Celery beat) -- kontrak Redis antara `apps/worker`
(PENULIS: `cti_worker.scheduler.CtiScheduler` tiap tick; PEMBACA: watchdog
di proses worker) dan `apps/api` (PEMBACA: `GET /api/scraper` +
`GET /api/scraper/health` -> banner di `/scrapers`).

Kenapa ada: insiden staging 2026-09-26 15:42 -> 2026-09-30 17:17 UTC (~97,6
jam) -- container `beat` di-stop manual habis rehearsal 60 menit dan gak
pernah dinyalain lagi. Gak ada satu pun sinyal yang nangkep: UI cuma nampilin
cron mentah + "Last Run", dan digest health (`scraper.health_digest`) itu
sendiri DIJADWALKAN beat -- beat mati = digest ikut diam, padahal "diam"
didefinisikan "sehat". Heartbeat ini sinyal yang hidup DI LUAR beat.

Fungsi di sini MURNI (encode/parse/klasifikasi) -- I/O Redis ada di caller,
biar API (redis.asyncio) dan worker (redis sync) numpang logic yang sama."""

from __future__ import annotations

import datetime
import json
from dataclasses import dataclass
from typing import Literal

HEARTBEAT_KEY = "cti:beat:heartbeat"
"""Nilai JSON `{"last_tick": iso, "started_at": iso}`, TANPA TTL -- nilai
basi justru informasinya ("terakhir hidup jam segini"). Redis staging/prod
pakai AOF, jadi selamat dari restart Redis."""

SchedulerState = Literal["ok", "stale", "unknown"]


@dataclass(frozen=True)
class BeatHeartbeat:
    last_tick: datetime.datetime
    started_at: datetime.datetime | None


@dataclass(frozen=True)
class SchedulerStatus:
    state: SchedulerState
    """ok = tick terakhir masih dalam ambang; stale = lewat ambang (beat mati/
    macet); unknown = heartbeat gak pernah ketulis (beat belum pernah jalan
    dengan kode ini, atau key-nya hilang) -- diperlakukan sama seriusnya
    dengan `stale` oleh UI/watchdog, cuma pesannya beda."""
    last_tick: datetime.datetime | None
    started_at: datetime.datetime | None
    age_s: float | None
    stale_after_s: int


def encode(last_tick: datetime.datetime, started_at: datetime.datetime | None) -> str:
    return json.dumps(
        {
            "last_tick": last_tick.isoformat(),
            "started_at": started_at.isoformat() if started_at else None,
        }
    )


def _parse_dt(raw: object) -> datetime.datetime | None:
    if not isinstance(raw, str):
        return None
    try:
        dt = datetime.datetime.fromisoformat(raw)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=datetime.UTC)


def parse(raw: str | bytes | None) -> BeatHeartbeat | None:
    """`None` kalau key gak ada ATAU isinya rusak -- rusak diperlakukan sama
    dengan "gak ada heartbeat", bukan exception yang bikin endpoint 500."""
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    last_tick = _parse_dt(data.get("last_tick"))
    if last_tick is None:
        return None
    return BeatHeartbeat(last_tick=last_tick, started_at=_parse_dt(data.get("started_at")))


def classify(
    heartbeat: BeatHeartbeat | None, *, now: datetime.datetime, stale_after_s: int
) -> SchedulerStatus:
    if heartbeat is None:
        return SchedulerStatus(
            state="unknown",
            last_tick=None,
            started_at=None,
            age_s=None,
            stale_after_s=stale_after_s,
        )
    age_s = (now - heartbeat.last_tick).total_seconds()
    return SchedulerStatus(
        state="stale" if age_s > stale_after_s else "ok",
        last_tick=heartbeat.last_tick,
        started_at=heartbeat.started_at,
        age_s=age_s,
        stale_after_s=stale_after_s,
    )
