"""Waktu lokal laporan. Beat berjalan UTC, tapi laporan lama mengikuti jam LOKAL
server Rundeck (WIB) -- "hari ini" untuk counter harian berakhir 23:55 WIB, bukan
23:55 UTC. Semuanya lewat `WorkerSettings.report_utc_offset_hours`."""

from __future__ import annotations

import datetime


def local_now(offset_hours: int, *, now_utc: datetime.datetime | None = None) -> datetime.datetime:
    """Waktu lokal (aware, tz = UTC+offset)."""
    tz = datetime.timezone(datetime.timedelta(hours=offset_hours))
    now = now_utc or datetime.datetime.now(datetime.UTC)
    return now.astimezone(tz)


def local_day_bounds_utc(
    local_date: datetime.date, offset_hours: int
) -> tuple[datetime.datetime, datetime.datetime]:
    """[awal, akhir) hari lokal `local_date`, dinyatakan dalam UTC (aware)."""
    tz = datetime.timezone(datetime.timedelta(hours=offset_hours))
    start_local = datetime.datetime.combine(local_date, datetime.time.min, tzinfo=tz)
    start = start_local.astimezone(datetime.UTC)
    return start, start + datetime.timedelta(days=1)


def local_to_utc_cron(
    hour: int, minute: int, offset_hours: int, weekday: int | None = None
) -> dict[str, int]:
    """Jam lokal -> argumen `crontab(...)` UTC. `weekday` 0=Senin..6=Minggu
    (konvensi Python); hasil `day_of_week` memakai konvensi cron 0=Minggu..6=Sabtu
    dan ikut bergeser kalau konversi melewati tengah malam."""
    total = hour * 60 + minute - offset_hours * 60
    day_shift, minutes_of_day = divmod(total, 24 * 60)
    out = {"hour": minutes_of_day // 60, "minute": minutes_of_day % 60}
    if weekday is not None:
        cron_local = (weekday + 1) % 7  # Senin(0) -> 1 ... Minggu(6) -> 0
        out["day_of_week"] = (cron_local + day_shift) % 7
    return out
