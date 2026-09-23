"""Integration test `cti_api.services.geopolitical.get_geopolitical_
summary` -- Postgres REAL (testcontainers). Fase 7.4 Grup A
(2026-09-23)."""

from __future__ import annotations

import datetime

import pytest
from cti_api.services import geopolitical as svc
from cti_core.db.repositories.ta import AsyncTAProfileRepo
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio

_TODAY = datetime.date.today()


async def test_empty_campaigns_returns_zeroed_summary(async_db_session: AsyncSession) -> None:
    result = await svc.get_geopolitical_summary(async_db_session, [], days=30)
    assert result["nation_state_activity"] == {}
    assert result["campaign_count"] == 0
    assert result["geopolitical_alerts"] == []


async def test_nation_state_activity_grouped_by_sponsoring_nation(
    async_db_session: AsyncSession,
) -> None:
    await AsyncTAProfileRepo(async_db_session).save_profile(
        "Apt41",
        {
            "identity": {"sponsoring_nation": "China", "actor_type": "state-sponsored"},
            "motivation": {"primary_motivation": "espionage"},
        },
    )
    campaigns = [
        {
            "cluster_id": "c1",
            "dominant_tas": ["Apt41"],
            "dominant_industries": ["Manufacturing"],
            "dominant_countries": ["US"],
            "last_seen": _TODAY.isoformat(),
        }
    ]

    result = await svc.get_geopolitical_summary(async_db_session, campaigns, days=30)
    assert "China" in result["nation_state_activity"]
    entry = result["nation_state_activity"]["China"]
    assert entry["campaign_count"] == 1
    assert entry["primary_motivations"] == ["espionage"]
    assert entry["targeted_sectors"] == ["Manufacturing"]
    assert result["motivation_breakdown"] == {"espionage": 1}


async def test_unknown_nation_excluded_from_alerts(async_db_session: AsyncSession) -> None:
    """TA tanpa profile -> nation "Unknown" -- masuk `nation_state_
    activity` tapi TIDAK memicu alert (port apa adanya, `if nation ==
    "Unknown": continue`)."""
    campaigns = [
        {
            "cluster_id": "c1",
            "dominant_tas": ["UnknownActor"],
            "dominant_industries": [],
            "dominant_countries": [],
            "last_seen": _TODAY.isoformat(),
        }
    ]
    result = await svc.get_geopolitical_summary(async_db_session, campaigns, days=30)
    assert "Unknown" in result["nation_state_activity"]
    assert result["geopolitical_alerts"] == []


async def test_sector_trend_increasing_generates_alert(async_db_session: AsyncSession) -> None:
    old_date = (_TODAY - datetime.timedelta(days=45)).isoformat()
    campaigns = [
        {
            "cluster_id": f"prior-{i}",
            "dominant_tas": [],
            "dominant_industries": ["Finance"],
            "dominant_countries": [],
            "last_seen": old_date,
        }
        for i in range(1)
    ] + [
        {
            "cluster_id": f"recent-{i}",
            "dominant_tas": [],
            "dominant_industries": ["Finance"],
            "dominant_countries": [],
            "last_seen": _TODAY.isoformat(),
        }
        for i in range(3)
    ]

    result = await svc.get_geopolitical_summary(async_db_session, campaigns, days=30)
    trend = result["sector_threat_trends"]["Finance"]
    assert trend["trend"] == "increasing"
    assert trend["campaign_count"] == 3
    assert trend["prior_count"] == 1
    assert any("Finance" in a for a in result["geopolitical_alerts"])


async def test_nation_state_alert_requires_at_least_3_campaigns(
    async_db_session: AsyncSession,
) -> None:
    await AsyncTAProfileRepo(async_db_session).save_profile(
        "Lazarus", {"identity": {"sponsoring_nation": "North Korea"}}
    )
    campaigns = [
        {
            "cluster_id": f"c{i}",
            "dominant_tas": ["Lazarus"],
            "dominant_industries": [],
            "dominant_countries": [],
            "last_seen": _TODAY.isoformat(),
        }
        for i in range(2)
    ]
    result = await svc.get_geopolitical_summary(async_db_session, campaigns, days=30)
    assert not any("North Korea" in a for a in result["geopolitical_alerts"])
