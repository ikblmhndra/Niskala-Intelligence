"""Integration test `AsyncClusterRepo` + `cti_api.services.cluster`
(Pipeline 1 -- greedy TF-IDF, persisted) -- Postgres REAL
(testcontainers). Fase 7.4 Grup A (2026-09-23)."""

from __future__ import annotations

import datetime

import pytest
from cti_api.services import cluster as cluster_service
from cti_core.db.models.cluster import Cluster
from cti_core.db.repositories.article import AsyncArticleRepo
from cti_core.db.repositories.cluster import AsyncClusterRepo
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio

_TODAY = datetime.date.today()


_SIMILAR_TITLES = [
    "Apt41 threat group breaches manufacturing sector networks United",
    "Apt41 threat group breaches manufacturing sector networks Europe",
    "Apt41 threat group breaches manufacturing sector networks Japan",
]


async def _seed_similar_articles(session: AsyncSession, n: int = 3) -> None:
    repo = AsyncArticleRepo(session)
    for i in range(n):
        await repo.upsert(
            url=f"https://example.com/apt41-{i}",
            title=_SIMILAR_TITLES[i % len(_SIMILAR_TITLES)],
            source=f"Source{i}",
            posted_on=_TODAY,
        )


# ── AsyncClusterRepo ──────────────────────────────────────────────────────────


async def test_upsert_and_tag_creates_new_cluster(async_db_session: AsyncSession) -> None:
    repo = AsyncClusterRepo(async_db_session)
    clusters = [{"cluster_id": "abc123", "cluster_name": "Test Cluster", "article_count": 3}]

    await repo.upsert_and_tag(clusters, today=_TODAY)

    row = await repo.get_by_cluster_id("abc123")
    assert row is not None
    assert row.cluster_name == "Test Cluster"
    assert row.first_seen == _TODAY
    assert row.last_seen == _TODAY
    assert row.last_count == 3
    assert row.peak_count == 3
    assert len(row.daily_counts) == 1
    assert clusters[0]["re_emerged"] is False


async def test_upsert_and_tag_updates_existing_and_tracks_peak(
    async_db_session: AsyncSession,
) -> None:
    repo = AsyncClusterRepo(async_db_session)
    await repo.upsert_and_tag(
        [{"cluster_id": "abc123", "cluster_name": "Test", "article_count": 5}], today=_TODAY
    )
    tomorrow = _TODAY + datetime.timedelta(days=1)
    await repo.upsert_and_tag(
        [{"cluster_id": "abc123", "cluster_name": "Test", "article_count": 2}], today=tomorrow
    )

    row = await repo.get_by_cluster_id("abc123")
    assert row is not None
    assert row.last_count == 2
    assert row.peak_count == 5  # tetap max, gak ketimpa turun
    assert row.last_seen == tomorrow
    assert row.first_seen == _TODAY  # gak berubah
    assert len(row.daily_counts) == 2


async def test_upsert_and_tag_detects_re_emerged(async_db_session: AsyncSession) -> None:
    repo = AsyncClusterRepo(async_db_session)
    await repo.upsert_and_tag(
        [{"cluster_id": "abc123", "cluster_name": "Test", "article_count": 3}], today=_TODAY
    )
    ten_days_later = _TODAY + datetime.timedelta(days=10)
    clusters = [{"cluster_id": "abc123", "cluster_name": "Test", "article_count": 4}]
    await repo.upsert_and_tag(clusters, today=ten_days_later)

    assert clusters[0]["re_emerged"] is True


async def test_upsert_and_tag_daily_counts_capped_at_90(async_db_session: AsyncSession) -> None:
    repo = AsyncClusterRepo(async_db_session)
    day = _TODAY - datetime.timedelta(days=95)
    for i in range(95):
        await repo.upsert_and_tag(
            [{"cluster_id": "abc123", "cluster_name": "Test", "article_count": 1}],
            today=day + datetime.timedelta(days=i),
        )
    row = await repo.get_by_cluster_id("abc123")
    assert row is not None
    assert len(row.daily_counts) == 90


async def test_list_seen_since_filters_by_last_seen(async_db_session: AsyncSession) -> None:
    async_db_session.add_all(
        [
            Cluster(
                cluster_id="recent",
                cluster_name="Recent",
                first_seen=_TODAY,
                last_seen=_TODAY,
                last_count=1,
                peak_count=1,
                daily_counts=[],
            ),
            Cluster(
                cluster_id="old",
                cluster_name="Old",
                first_seen=_TODAY - datetime.timedelta(days=100),
                last_seen=_TODAY - datetime.timedelta(days=100),
                last_count=1,
                peak_count=1,
                daily_counts=[],
            ),
        ]
    )
    await async_db_session.flush()

    rows = await AsyncClusterRepo(async_db_session).list_seen_since(
        _TODAY - datetime.timedelta(days=30)
    )
    assert [r.cluster_id for r in rows] == ["recent"]


# ── cti_api.services.cluster (Pipeline 1) ────────────────────────────────────


async def test_get_clusters_groups_similar_titles_and_persists(
    async_db_session: AsyncSession,
) -> None:
    await _seed_similar_articles(async_db_session, n=3)

    clusters = await cluster_service.get_clusters(async_db_session, days=30, threshold=0.3)
    assert len(clusters) == 1
    assert clusters[0]["article_count"] == 3
    assert clusters[0]["source_count"] == 3

    # dipersist ke tabel clusters
    row = await AsyncClusterRepo(async_db_session).get_by_cluster_id(clusters[0]["cluster_id"])
    assert row is not None
    assert row.last_count == 3


async def test_get_clusters_too_few_articles_returns_empty(
    async_db_session: AsyncSession,
) -> None:
    repo = AsyncArticleRepo(async_db_session)
    await repo.upsert(
        url="https://example.com/solo", title="Solo article", source="A", posted_on=_TODAY
    )

    clusters = await cluster_service.get_clusters(async_db_session, days=30)
    assert clusters == []


async def test_get_clusters_dissimilar_titles_not_grouped(async_db_session: AsyncSession) -> None:
    repo = AsyncArticleRepo(async_db_session)
    await repo.upsert(
        url="https://example.com/a",
        title="Ransomware hits hospital network today",
        source="A",
        posted_on=_TODAY,
    )
    await repo.upsert(
        url="https://example.com/b",
        title="Zero-day exploited in popular browser",
        source="B",
        posted_on=_TODAY,
    )

    clusters = await cluster_service.get_clusters(async_db_session, days=30, threshold=0.5)
    assert clusters == []  # masing-masing cluster cuma 1 artikel -> difilter


async def test_get_clusters_is_cached(async_db_session: AsyncSession) -> None:
    cluster_service._CACHE.clear()
    await _seed_similar_articles(async_db_session, n=3)

    first = await cluster_service.get_clusters(async_db_session, days=30, threshold=0.3)
    assert len(first) == 1

    # tambah artikel baru TANPA invalidate cache -- hasil harus SAMA
    repo = AsyncArticleRepo(async_db_session)
    await repo.upsert(
        url="https://example.com/apt41-extra",
        title="Apt41 breaches manufacturing sector target extra",
        source="SourceExtra",
        posted_on=_TODAY,
    )
    cached = await cluster_service.get_clusters(async_db_session, days=30, threshold=0.3)
    assert cached[0]["article_count"] == 3  # masih cache lama
    cluster_service._CACHE.clear()
