"""Integration test `AsyncNewsletterRepo` -- Postgres REAL
(testcontainers). Fase 7.3 (router `newsletter`, Bagian 4)."""

from __future__ import annotations

import pytest
from cti_core.db.repositories.newsletter import AsyncNewsletterRepo
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio


async def test_save_and_get_by_id(async_db_session: AsyncSession) -> None:
    repo = AsyncNewsletterRepo(async_db_session)
    row = await repo.save(
        week=38,
        year=2026,
        generated_at="2026-09-19 10:00 UTC",
        created_by="analyst1",
        html="<html>digest</html>",
        sections={"highlight": {"title": "t1"}, "apac": [], "global_news": [], "indonesia": []},
    )
    assert row.id is not None

    fetched = await repo.get_by_id(row.id)
    assert fetched is not None
    assert fetched.week == 38
    assert fetched.sections["highlight"]["title"] == "t1"


async def test_get_html(async_db_session: AsyncSession) -> None:
    repo = AsyncNewsletterRepo(async_db_session)
    row = await repo.save(
        week=1,
        year=2026,
        generated_at="x",
        created_by="a",
        html="<html>hi</html>",
        sections={},
    )
    assert await repo.get_html(row.id) == "<html>hi</html>"
    assert await repo.get_html(999999) is None


async def test_list_all_newest_first_paginated(async_db_session: AsyncSession) -> None:
    repo = AsyncNewsletterRepo(async_db_session)
    for week in (1, 2, 3):
        await repo.save(
            week=week, year=2026, generated_at="x", created_by="a", html="<html/>", sections={}
        )

    rows, total = await repo.list_all(page=1, page_size=2)
    assert total == 3
    assert len(rows) == 2
    assert rows[0].week == 3  # created_at desc -- terakhir disimpen duluan


async def test_paywall_hint_upsert_and_list(async_db_session: AsyncSession) -> None:
    repo = AsyncNewsletterRepo(async_db_session)
    await repo.upsert_paywall_hint("example.com", last_seen="2026-09-18T00:00:00Z")
    await repo.upsert_paywall_hint("example.com", last_seen="2026-09-19T00:00:00Z")

    hint = await repo.get_paywall_hint("example.com")
    assert hint is not None
    assert hint.last_seen == "2026-09-19T00:00:00Z"

    hints = await repo.get_all_paywall_hints()
    assert hints["example.com"]["paywall_likely"] is True
    assert hints["example.com"]["last_seen"] == "2026-09-19T00:00:00Z"


async def test_get_all_paywall_hints_empty(async_db_session: AsyncSession) -> None:
    repo = AsyncNewsletterRepo(async_db_session)
    assert await repo.get_all_paywall_hints() == {}
