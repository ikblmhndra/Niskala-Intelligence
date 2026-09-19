"""Integration test `AsyncRecapRepo` -- Postgres REAL (testcontainers).
Fase 7.3 (router `recap`, Bagian 5)."""

from __future__ import annotations

import datetime

import pytest
from cti_core.db.repositories.recap import AsyncRecapRepo
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio


async def test_upsert_creates_then_updates(async_db_session: AsyncSession) -> None:
    repo = AsyncRecapRepo(async_db_session)
    row = await repo.upsert(
        "2026-09-18",
        headline="quiet day",
        yesterday={"summary": "nothing much"},
        forecast={},
        counts={"articles": 0},
        generated_at=datetime.datetime.now(datetime.UTC),
        model="test-model",
        token_usage={},
        raw_llm=None,
    )
    assert row.headline == "quiet day"

    updated = await repo.upsert("2026-09-18", headline="actually busy", counts={"articles": 5})
    assert updated.id == row.id
    assert updated.headline == "actually busy"
    assert updated.counts == {"articles": 5}


async def test_get_missing_returns_none(async_db_session: AsyncSession) -> None:
    assert await AsyncRecapRepo(async_db_session).get("2026-01-01") is None


async def test_list_recent_ordered_desc(async_db_session: AsyncSession) -> None:
    repo = AsyncRecapRepo(async_db_session)
    for d in ("2026-09-15", "2026-09-17", "2026-09-16"):
        await repo.upsert(
            d,
            headline=d,
            yesterday={},
            forecast={},
            counts={},
            generated_at=datetime.datetime.now(datetime.UTC),
            model="m",
            token_usage={},
            raw_llm=None,
        )
    rows = await repo.list_recent(limit=10)
    assert [r.date for r in rows] == ["2026-09-17", "2026-09-16", "2026-09-15"]
