"""`cti_worker.reports.timeutil` -- jam lokal Rundeck -> cron UTC (Fase 10.E)."""

from __future__ import annotations

import datetime

import pytest
from cti_worker.reports.timeutil import local_day_bounds_utc, local_now, local_to_utc_cron

UTC = datetime.UTC


@pytest.mark.parametrize(
    ("local", "offset", "expected"),
    [
        ((23, 55), 7, {"hour": 16, "minute": 55}),  # WIB 23:55 -> 16:55 UTC
        ((7, 0), 7, {"hour": 0, "minute": 0}),
        ((7, 1), 0, {"hour": 7, "minute": 1}),  # server ternyata UTC
        ((3, 30), 7, {"hour": 20, "minute": 30}),  # melewati tengah malam ke hari sebelumnya
        ((0, 15), -5, {"hour": 5, "minute": 15}),
    ],
)
def test_local_time_maps_to_utc_hour_and_minute(local, offset, expected) -> None:
    assert local_to_utc_cron(*local, offset) == expected


@pytest.mark.parametrize(
    ("weekday", "local", "offset", "cron_dow"),
    [
        (6, (7, 1), 7, 0),  # Minggu 07:01 WIB = Minggu 00:01 UTC -> cron 0
        (0, (7, 1), 7, 1),  # Senin 07:01 WIB -> Senin 00:01 UTC -> cron 1
        (0, (3, 0), 7, 0),  # Senin 03:00 WIB = MINGGU 20:00 UTC -> hari bergeser mundur
        (6, (3, 0), 7, 6),  # Minggu 03:00 WIB = SABTU 20:00 UTC
        (2, (23, 0), -5, 4),  # Rabu 23:00 UTC-5 = KAMIS 04:00 UTC -> hari maju
    ],
)
def test_weekday_shifts_with_the_conversion(weekday, local, offset, cron_dow) -> None:
    assert local_to_utc_cron(*local, offset, weekday=weekday)["day_of_week"] == cron_dow


def test_local_day_bounds_cover_exactly_24_hours_in_utc() -> None:
    start, end = local_day_bounds_utc(datetime.date(2026, 9, 26), 7)

    assert start == datetime.datetime(2026, 9, 25, 17, 0, tzinfo=UTC)  # 00:00 WIB
    assert end == datetime.datetime(2026, 9, 26, 17, 0, tzinfo=UTC)


def test_local_now_uses_the_offset_for_the_calendar_day() -> None:
    now_utc = datetime.datetime(2026, 9, 25, 20, 0, tzinfo=UTC)  # 03:00 WIB tanggal 26

    assert local_now(7, now_utc=now_utc).date() == datetime.date(2026, 9, 26)
    assert local_now(0, now_utc=now_utc).date() == datetime.date(2026, 9, 25)
