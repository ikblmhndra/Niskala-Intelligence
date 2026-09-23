"""Integration test `cti_api.services.campaign_trend` -- Postgres REAL
(testcontainers). Fase 7.4 Grup A (2026-09-23)."""

from __future__ import annotations

import datetime

import pytest
from cti_api.services import campaign_trend as svc
from cti_core.db.models.cluster import Cluster
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio

_TODAY = datetime.date.today()


def _daily(offsets_counts: list[tuple[int, int]]) -> list[dict[str, object]]:
    return [
        {
            "date": (_TODAY - datetime.timedelta(days=off)).isoformat(),
            "count": cnt,
            "new_iocs": 0,
            "new_tas": 0,
        }
        for off, cnt in offsets_counts
    ]


async def test_get_campaign_trends_missing_cluster_returns_empty(
    async_db_session: AsyncSession,
) -> None:
    assert await svc.get_campaign_trends(async_db_session, "nonexistent") == {}


async def test_get_campaign_trends_growing() -> None:
    assert svc._trend_direction(0.5, 5.0) == "growing"


async def test_get_campaign_trends_dormant_when_recent_avg_low() -> None:
    assert svc._trend_direction(1.0, 0.2) == "dormant"


async def test_get_campaign_trends_declining() -> None:
    assert svc._trend_direction(-0.5, 5.0) == "declining"


async def test_get_campaign_trends_stable() -> None:
    assert svc._trend_direction(0.1, 5.0) == "stable"


async def test_get_campaign_trends_computes_growth_rate(async_db_session: AsyncSession) -> None:
    # prior week (offset 13..7) flat rendah, last week (offset 6..0) NAIK
    # hari demi hari -- `trend_direction` itu slope DALAM last7 doang
    # (bukan week-over-week, itu `growth_rate`'s job), jadi last7 emang
    # perlu miring naik buat "growing".
    prior_week = [(13, 1), (12, 1), (11, 1), (10, 1), (9, 1), (8, 1), (7, 1)]  # sum 7
    last_week = [(6, 1), (5, 2), (4, 3), (3, 3), (2, 3), (1, 4), (0, 5)]  # naik, sum 21
    daily = _daily([*prior_week, *last_week])
    async_db_session.add(
        Cluster(
            cluster_id="trend1",
            cluster_name="Trending Cluster",
            first_seen=_TODAY - datetime.timedelta(days=13),
            last_seen=_TODAY,
            last_count=3,
            peak_count=3,
            daily_counts=daily,
        )
    )
    await async_db_session.flush()

    trend = await svc.get_campaign_trends(async_db_session, "trend1")
    assert trend["cluster_name"] == "Trending Cluster"
    assert trend["growth_rate"] == 200.0  # (21-7)/7*100
    assert trend["trend_direction"] == "growing"
    assert len(trend["timeline"]) == 14


async def test_get_campaign_trends_excludes_entries_older_than_90_days(
    async_db_session: AsyncSession,
) -> None:
    daily = _daily([(100, 5), (1, 2)])
    async_db_session.add(
        Cluster(
            cluster_id="old_entries",
            cluster_name="Old",
            first_seen=_TODAY - datetime.timedelta(days=100),
            last_seen=_TODAY,
            last_count=2,
            peak_count=5,
            daily_counts=daily,
        )
    )
    await async_db_session.flush()

    trend = await svc.get_campaign_trends(async_db_session, "old_entries")
    assert len(trend["timeline"]) == 1  # cuma yang <=90 hari


async def test_get_campaign_evolution_sorted_by_growth_rate(
    async_db_session: AsyncSession,
) -> None:
    async_db_session.add_all(
        [
            Cluster(
                cluster_id="fast",
                cluster_name="Fast Growth",
                first_seen=_TODAY - datetime.timedelta(days=13),
                last_seen=_TODAY,
                last_count=5,
                peak_count=5,
                daily_counts=_daily([(7, 1)] + [(i, 5) for i in range(7)]),
            ),
            Cluster(
                cluster_id="slow",
                cluster_name="Slow Growth",
                first_seen=_TODAY - datetime.timedelta(days=13),
                last_seen=_TODAY,
                last_count=1,
                peak_count=1,
                daily_counts=_daily([(7, 1)] + [(i, 1) for i in range(7)]),
            ),
        ]
    )
    await async_db_session.flush()

    results = await svc.get_campaign_evolution(async_db_session, days=30)
    assert [r["cluster_id"] for r in results] == ["fast", "slow"]
