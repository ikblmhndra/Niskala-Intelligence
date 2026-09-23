"""Integration test `cti_api.services.newsletter.build_newsletter_
context()`'s `include_clusters`/`campaign_clusters` wiring (Fase 7.4
Grup A, 2026-09-23) -- Postgres REAL (testcontainers), tapi
`_enrich_articles()` (Playwright real browser) DAN `get_recent_
campaigns()` di-mock biar test ini fokus ke mapping `campaign_clusters`
doang, bukan re-test clustering/enrichment yang udah dites terpisah."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from cti_api.services import newsletter as newsletter_service
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio

_ARTICLE = {"id": 1, "title": "Highlight article", "url": "https://example.com/1", "source": "A"}

_FAKE_CAMPAIGNS = [
    {
        "cluster_id": f"c{i}",
        "summary_title": f"Campaign {i}",
        "size": 3,
        "first_seen": "2026-09-01",
        "last_seen": "2026-09-10",
        "dominant_tas": ["Apt41"],
        "dominant_industries": ["Manufacturing"],
        "dominant_countries": ["US"],
        "attack_techniques": ["T1566"],
        "cve_ids": ["CVE-2026-0001"],
    }
    for i in range(7)
]


async def test_include_clusters_false_returns_empty_campaign_clusters(
    async_db_session: AsyncSession,
) -> None:
    with patch.object(newsletter_service, "_enrich_articles", AsyncMock(return_value=[_ARTICLE])):
        context = await newsletter_service.build_newsletter_context(
            async_db_session, _ARTICLE, [], [], [], include_clusters=False
        )
    assert context["campaign_clusters"] == []


async def test_include_clusters_true_maps_top_5_campaigns(
    async_db_session: AsyncSession,
) -> None:
    with (
        patch.object(newsletter_service, "_enrich_articles", AsyncMock(return_value=[_ARTICLE])),
        patch.object(
            newsletter_service.campaign_service,
            "get_recent_campaigns",
            AsyncMock(return_value=_FAKE_CAMPAIGNS),
        ) as mock_campaigns,
    ):
        context = await newsletter_service.build_newsletter_context(
            async_db_session, _ARTICLE, [], [], [], include_clusters=True, cluster_days=7
        )

    mock_campaigns.assert_awaited_once_with(async_db_session, days=7, min_size=3)
    clusters = context["campaign_clusters"]
    assert len(clusters) == 5  # dipotong 5 teratas, port apa adanya
    assert clusters[0]["name"] == "Campaign 0"
    assert clusters[0]["dominant_tas"] == ["Apt41"]
    assert clusters[0]["cve_ids"] == ["CVE-2026-0001"]
