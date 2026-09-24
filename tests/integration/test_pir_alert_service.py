"""Integration test `cti_api.services.pir_alert` -- Fase 7.8 (Celery beat
"PIR alert", salah satu dari 5 loop). Postgres REAL (testcontainers).

Fokus test: `created_at_start` (BUKAN `posted_on`) yang nentuin "baru
sejak tick terakhir", PIR yang lewat jendela aktif di-skip, PIR tanpa
kriteria di-skip, dan partisi `only_priority`/`exclude_priority` gak
overlap -- lihat docstring modul buat alasan desainnya."""

from __future__ import annotations

import datetime

import pytest
from cti_api.services.pir_alert import check_new_articles_vs_pirs, format_pir_alert
from cti_core.db.repositories.article import AsyncArticleRepo
from cti_core.db.repositories.auth import AsyncClientRepo
from cti_core.db.repositories.pir import AsyncPIRRepo
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio

_NOW = datetime.datetime.now(datetime.UTC)


async def _seed_pir(
    session: AsyncSession,
    *,
    priority: str = "P2",
    criteria: dict[str, list[str]] | None = None,
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
) -> int:
    await AsyncClientRepo(session).ensure_default()
    pir = await AsyncPIRRepo(session).create(
        {
            "title": "Track APT41",
            "priority": priority,
            "criteria": criteria if criteria is not None else {"threat_actors": ["Apt41"]},
            "start_date": start_date,
            "end_date": end_date,
        },
        client_id="default",
    )
    return pir.id


async def _seed_article(session: AsyncSession, *, created_at: datetime.datetime, url: str) -> None:
    repo = AsyncArticleRepo(session)
    article = await repo.upsert(
        url=url,
        title="Apt41 breaches government network",
        source="gbhacker",
        posted_on=_NOW.date(),
    )
    await repo.set_enrichment(article, threat_actors=["Apt41"])
    article.created_at = created_at
    await session.flush()


async def test_only_matches_articles_created_since_cutoff(async_db_session: AsyncSession) -> None:
    await _seed_pir(async_db_session)
    await _seed_article(
        async_db_session,
        created_at=_NOW - datetime.timedelta(hours=2),
        url="https://example.com/old",
    )
    await _seed_article(async_db_session, created_at=_NOW, url="https://example.com/new")

    results = await check_new_articles_vs_pirs(
        async_db_session, since=_NOW - datetime.timedelta(minutes=5)
    )

    assert len(results) == 1
    urls = {a.url for a in results[0]["articles"]}
    assert urls == {"https://example.com/new"}


async def test_pir_without_criteria_is_skipped(async_db_session: AsyncSession) -> None:
    await _seed_pir(async_db_session, criteria={})
    await _seed_article(async_db_session, created_at=_NOW, url="https://example.com/a")

    results = await check_new_articles_vs_pirs(
        async_db_session, since=_NOW - datetime.timedelta(minutes=5)
    )
    assert results == []


async def test_pir_outside_active_window_is_skipped(async_db_session: AsyncSession) -> None:
    yesterday = _NOW.date() - datetime.timedelta(days=1)
    await _seed_pir(async_db_session, end_date=yesterday)
    await _seed_article(async_db_session, created_at=_NOW, url="https://example.com/a")

    results = await check_new_articles_vs_pirs(
        async_db_session, since=_NOW - datetime.timedelta(minutes=5)
    )
    assert results == []


async def test_only_priority_and_exclude_priority_partition_without_overlap(
    async_db_session: AsyncSession,
) -> None:
    await _seed_pir(async_db_session, priority="P1")
    await _seed_pir(async_db_session, priority="P2")
    await _seed_article(async_db_session, created_at=_NOW, url="https://example.com/a")

    since = _NOW - datetime.timedelta(minutes=5)
    p1_only = await check_new_articles_vs_pirs(async_db_session, since=since, only_priority="P1")
    not_p1 = await check_new_articles_vs_pirs(async_db_session, since=since, exclude_priority="P1")

    assert [r["pir"].priority for r in p1_only] == ["P1"]
    assert [r["pir"].priority for r in not_p1] == ["P2"]


async def test_format_pir_alert_marks_p1_critical() -> None:
    from types import SimpleNamespace

    pir = SimpleNamespace(priority="P1", title="Track APT41", owner="analyst1")
    article = SimpleNamespace(
        url="https://example.com/a",
        title="Apt41 breaches network",
        source="gbhacker",
        posted_on=_NOW.date(),
        news_type="apt",
    )
    msg = format_pir_alert(pir, [article])
    assert "CRITICAL" in msg
    assert "Track APT41" in msg
    assert "analyst1" in msg
    assert "Apt41 breaches network" in msg
