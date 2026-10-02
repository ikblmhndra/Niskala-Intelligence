"""Cadence empat scraper Twitter harus sama dengan Rundeck asli
(`docs/legacy/rundeck-jobs-map.json`).

Keempatnya berbagi satu saldo twitterapi.io. `monitor_x` sempat jalan `*/15` padahal legacy `0/3`
jam (12x lebih sering): kredit kunci baru habis ~3 jam sesudah dipasang di staging (2026-10-01),
120 run gagal `HTTP 402` semalam. Nilai di bawah SENGAJA ditulis literal (bukan dibaca dari file)
supaya mengubah cadence harus disengaja dan terlihat di diff."""

from __future__ import annotations

import datetime

import pytest
from cti_scraper import registry
from cti_scraper.health import expected_interval

NOW = datetime.datetime(2026, 10, 2, 5, 30, tzinfo=datetime.UTC)

LEGACY_INTERVAL = {
    "monitor_x": datetime.timedelta(hours=3),  # monitorX.py: jam 0/3
    "trending_cve": datetime.timedelta(minutes=15),  # trendingCve.py: menit 0/15
    "tweet_alerts_1h": datetime.timedelta(hours=1),  # twitter.py: menit 0, tiap jam
    "tweet_alerts_30m": datetime.timedelta(hours=1),  # twitter30.py: menit 30, tiap jam
}


@pytest.mark.parametrize("scraper_id", sorted(LEGACY_INTERVAL))
def test_interval_sama_dengan_legacy(scraper_id: str) -> None:
    meta = registry.discover()[scraper_id].meta
    assert expected_interval(meta.schedule, now=NOW) == LEGACY_INTERVAL[scraper_id]


def test_monitor_x_tidak_menembak_bareng_scraper_twitter_lain() -> None:
    """Menit 8 bukan kelipatan 5 -- trending_cve (:00/:15/:30/:45), tweet_alerts_1h (:05),
    tweet_alerts_30m (:35) dan `monitor_x` (run ~6 menit) berebut bucket `10/minute` yang sama
    kalau bertumpuk."""
    meta = registry.discover()["monitor_x"].meta
    minute = int(meta.schedule.split()[0])
    assert minute % 5 != 0
