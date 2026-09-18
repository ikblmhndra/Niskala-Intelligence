"""Integration test `AsyncRansomwareVictimRepo` -- Postgres REAL
(testcontainers). Fase 7.3 (router `ransomware`)."""

from __future__ import annotations

import datetime

import pytest
from cti_core.db.models.article import Article, ArticleThreatActor
from cti_core.db.models.ransomware import RansomwareVictim
from cti_core.db.repositories.ransomware import AsyncRansomwareVictimRepo
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio


async def _seed_victims(session: AsyncSession) -> None:
    session.add(
        RansomwareVictim(
            offset_key="lockbit:acme-corp:US:2026-09-01",
            group_name="LockBit",
            victim="Acme Corp",
            country_code="US",
            industry="Manufacturing",
            published=datetime.date(2026, 9, 1),
        )
    )
    session.add(
        RansomwareVictim(
            offset_key="alphv:globex:ID:2026-09-05",
            group_name="ALPHV",
            victim="Globex",
            country_code="ID",
            industry="Finance",
            published=datetime.date(2026, 9, 5),
        )
    )
    await session.flush()


async def test_list_filtered_no_filters(async_db_session: AsyncSession) -> None:
    await _seed_victims(async_db_session)
    victims, total = await AsyncRansomwareVictimRepo(async_db_session).list_filtered()
    assert total == 2
    # published desc
    assert victims[0].group_name == "ALPHV"


async def test_list_filtered_by_group(async_db_session: AsyncSession) -> None:
    await _seed_victims(async_db_session)
    victims, total = await AsyncRansomwareVictimRepo(async_db_session).list_filtered(
        group="lockbit"
    )
    assert total == 1
    assert victims[0].victim == "Acme Corp"


async def test_list_filtered_by_country(async_db_session: AsyncSession) -> None:
    await _seed_victims(async_db_session)
    _, total = await AsyncRansomwareVictimRepo(async_db_session).list_filtered(country="ID")
    assert total == 1


async def test_list_filtered_by_industry(async_db_session: AsyncSession) -> None:
    await _seed_victims(async_db_session)
    _, total = await AsyncRansomwareVictimRepo(async_db_session).list_filtered(
        industry="finance"
    )
    assert total == 1


async def test_list_filtered_by_date_range(async_db_session: AsyncSession) -> None:
    await _seed_victims(async_db_session)
    _, total = await AsyncRansomwareVictimRepo(async_db_session).list_filtered(
        date_start=datetime.date(2026, 9, 3)
    )
    assert total == 1


async def test_get_filter_options(async_db_session: AsyncSession) -> None:
    await _seed_victims(async_db_session)
    options = await AsyncRansomwareVictimRepo(async_db_session).get_filter_options()
    assert options["groups"] == ["ALPHV", "LockBit"]
    assert options["countries"] == ["ID", "US"]
    assert options["industries"] == ["Finance", "Manufacturing"]


async def test_get_filter_options_empty(async_db_session: AsyncSession) -> None:
    options = await AsyncRansomwareVictimRepo(async_db_session).get_filter_options()
    assert options == {"groups": [], "countries": [], "industries": []}


async def test_get_related_articles_empty_when_no_victims(
    async_db_session: AsyncSession,
) -> None:
    articles, total = await AsyncRansomwareVictimRepo(async_db_session).get_related_articles()
    assert articles == []
    assert total == 0


async def test_get_related_articles_matches_by_threat_actor_tag(
    async_db_session: AsyncSession,
) -> None:
    await _seed_victims(async_db_session)
    article = Article(
        url="https://example.com/lockbit-news",
        url_hash="hash-lockbit",
        title="Some unrelated title",
        source="test",
    )
    article.threat_actors = [ArticleThreatActor(threat_actor="LockBit")]
    async_db_session.add(article)
    await async_db_session.flush()

    articles, total = await AsyncRansomwareVictimRepo(async_db_session).get_related_articles()
    assert total == 1
    assert articles[0].url == "https://example.com/lockbit-news"


async def test_get_related_articles_matches_by_title_substring(
    async_db_session: AsyncSession,
) -> None:
    await _seed_victims(async_db_session)
    article = Article(
        url="https://example.com/alphv-strikes",
        url_hash="hash-alphv",
        title="ALPHV strikes another victim",
        source="test",
    )
    async_db_session.add(article)
    await async_db_session.flush()

    articles, total = await AsyncRansomwareVictimRepo(async_db_session).get_related_articles()
    assert total == 1
    assert articles[0].url == "https://example.com/alphv-strikes"


async def test_get_related_articles_no_duplicate_when_matches_both(
    async_db_session: AsyncSession,
) -> None:
    """Artikel yang cocok LEWAT threat_actor DAN title (mis. nama grup ada
    di keduanya) harus tetap muncul SEKALI -- `.distinct()` di query."""
    await _seed_victims(async_db_session)
    article = Article(
        url="https://example.com/lockbit-both",
        url_hash="hash-lockbit-both",
        title="LockBit strikes again",
        source="test",
    )
    article.threat_actors = [ArticleThreatActor(threat_actor="LockBit")]
    async_db_session.add(article)
    await async_db_session.flush()

    articles, total = await AsyncRansomwareVictimRepo(async_db_session).get_related_articles()
    assert total == 1
    assert len(articles) == 1
