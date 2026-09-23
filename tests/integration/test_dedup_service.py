"""Integration test `cti_api.services.dedup.get_dedup_groups` -- Postgres
REAL (testcontainers). Fase 7.4 Grup D."""

from __future__ import annotations

import datetime

import pytest
from cti_api.services import dedup as svc
from cti_core.db.repositories.article import AsyncArticleRepo
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio

_TODAY = datetime.date.today()


async def test_get_dedup_groups_finds_near_duplicates(async_db_session: AsyncSession) -> None:
    repo = AsyncArticleRepo(async_db_session)
    await repo.upsert(
        url="https://a.com/1",
        title="Apt41 hits manufacturing sector hard",
        source="SourceA",
        posted_on=_TODAY,
    )
    await repo.upsert(
        url="https://b.com/1",
        title="Apt41 hits manufacturing sector hard!",
        source="SourceB",
        posted_on=_TODAY,
    )
    await repo.upsert(
        url="https://c.com/1",
        title="Completely unrelated zero-day story",
        source="SourceC",
        posted_on=_TODAY,
    )

    result = await svc.get_dedup_groups(async_db_session, days=7, threshold=0.5, limit=500)
    assert result["total_articles"] == 3
    assert result["total_groups"] == 1
    assert result["duplicates_suppressed"] == 1
    assert result["groups"][0]["_dup_count"] == 2


async def test_get_dedup_groups_respects_days_cutoff(async_db_session: AsyncSession) -> None:
    repo = AsyncArticleRepo(async_db_session)
    old_date = _TODAY - datetime.timedelta(days=30)
    await repo.upsert(
        url="https://a.com/old", title="Old article outside window", source="A", posted_on=old_date
    )

    result = await svc.get_dedup_groups(async_db_session, days=7, threshold=0.75, limit=500)
    assert result["total_articles"] == 0
    assert result["groups"] == []


async def test_get_dedup_groups_no_duplicates_returns_empty_groups(
    async_db_session: AsyncSession,
) -> None:
    repo = AsyncArticleRepo(async_db_session)
    await repo.upsert(
        url="https://a.com/x", title="Ransomware hits hospital", source="A", posted_on=_TODAY
    )
    await repo.upsert(
        url="https://b.com/x", title="Zero-day exploited in browser", source="B", posted_on=_TODAY
    )

    result = await svc.get_dedup_groups(async_db_session, days=7, threshold=0.75, limit=500)
    assert result["total_articles"] == 2
    assert result["total_groups"] == 0
    assert result["groups"] == []
