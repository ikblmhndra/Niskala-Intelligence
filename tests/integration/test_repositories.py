"""Integrasi repository lawan Postgres beneran (testcontainers), skema
lewat `alembic upgrade head` sungguhan -- bukan `create_all()`."""

from __future__ import annotations

import pytest
from cti_core.db.repositories.article import ArticleRepo, AsyncArticleRepo
from cti_core.db.repositories.ioc import IOCRepo
from cti_core.db.repositories.scraper import ScraperRunRepo
from cti_core.urlkit import url_hash
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session


def test_article_upsert_creates_then_updates(db_session: Session) -> None:
    repo = ArticleRepo(db_session)

    a1 = repo.upsert(url="https://example.com/x", title="Judul awal", source="Test")
    assert a1.seen_count == 1
    assert a1.url_hash == url_hash("https://example.com/x")

    # scrape ulang URL yang SAMA -- versi Mongo lama ($setOnInsert-only)
    # gak pernah update field ini; di sini HARUS update.
    a2 = repo.upsert(url="https://example.com/x", title="Judul diperbaiki", source="Test")
    assert a2.id == a1.id
    assert a2.title == "Judul diperbaiki"
    assert a2.seen_count == 2


def test_article_upsert_never_touches_overrides(db_session: Session) -> None:
    repo = ArticleRepo(db_session)
    article = repo.upsert(url="https://example.com/y", title="Asli", source="Test")

    repo.set_overrides(article, confidence_score=95, news_type="analyst_corrected")

    # scraper re-scrape -- overrides analis HARUS bertahan
    updated = repo.upsert(
        url="https://example.com/y", title="Asli v2", source="Test", confidence_score=10
    )
    assert updated.confidence_score == 10  # kolom mesin ke-timpa
    merged = repo.to_dict(updated)
    assert merged["confidence_score"] == 95  # tapi overrides yang menang
    assert merged["news_type"] == "analyst_corrected"


def test_article_upsert_rejects_identity_field_as_machine_field(db_session: Session) -> None:
    repo = ArticleRepo(db_session)
    with pytest.raises(ValueError, match="identitas"):
        repo.upsert(url="https://example.com/z", title="x", source="Test", url_hash="hacked")


def test_article_upsert_rejects_unknown_field(db_session: Session) -> None:
    repo = ArticleRepo(db_session)
    with pytest.raises(ValueError, match="bukan kolom"):
        repo.upsert(url="https://example.com/w", title="x", source="Test", this_typo_field=1)


def test_ioc_upsert_accumulates_sources_and_seen_count(db_session: Session) -> None:
    repo = IOCRepo(db_session)

    ioc = repo.upsert(
        type="domain", value="evil.example", source_url="https://a.com/1", source_name="A"
    )
    assert ioc.seen_count == 1
    assert len(ioc.sources) == 1

    ioc2 = repo.upsert(
        type="domain", value="evil.example", source_url="https://b.com/2", source_name="B"
    )
    assert ioc2.id == ioc.id
    assert ioc2.seen_count == 2
    assert len(ioc2.sources) == 2


def test_ioc_feedback_updates_tp_fp_counts(db_session: Session) -> None:
    repo = IOCRepo(db_session)
    ioc = repo.upsert(type="ip", value="1.2.3.4", source_url="https://a.com", source_name="A")

    repo.add_feedback(ioc, verdict="tp", submitted_by="analyst1")
    repo.add_feedback(ioc, verdict="fp", submitted_by="analyst2", note="allowlisted CDN")

    assert ioc.tp_count == 1
    assert ioc.fp_count == 1
    assert len(ioc.feedback) == 2


def test_scraper_run_lifecycle_distinguishes_empty_from_crash(db_session: Session) -> None:
    """Ini KEMAMPUAN yang gak ada di sistem lama -- scraper_runs lama cuma
    kebentuk kalau ada artikel diterima, jadi nol-item vs crash gak
    kebedain (lihat plan §8.1)."""
    repo = ScraperRunRepo(db_session)

    empty_run = repo.start(run_id="run-empty-1", scraper_id="gbhackers", trigger="beat")
    repo.finish(empty_run, status="empty", items_found=0)
    assert empty_run.status == "empty"
    assert empty_run.finished_at is not None
    assert empty_run.duration_ms is not None and empty_run.duration_ms >= 0

    crash_run = repo.start(run_id="run-crash-1", scraper_id="gbhackers", trigger="beat")
    repo.finish(
        crash_run,
        status="parse_error",
        items_found=0,
        errors=[{"stage": "parse", "message": "XPath matched nothing"}],
    )
    assert crash_run.status == "parse_error"
    assert crash_run.errors[0]["message"] == "XPath matched nothing"

    # dua run beda scraper_id yang sama, status beda -- kebedain lewat query
    fetched = repo.get_by_run_id("run-crash-1")
    assert fetched is not None
    assert fetched.status == "parse_error"


def test_scraper_run_rejects_unknown_status(db_session: Session) -> None:
    repo = ScraperRunRepo(db_session)
    run = repo.start(run_id="run-bad-status", scraper_id="x")
    with pytest.raises(ValueError, match="status terminal"):
        repo.finish(run, status="not_a_real_status")


async def test_async_article_repo_upsert_works(async_db_session: AsyncSession) -> None:
    """Jalur async (dipakai FastAPI, Fase 7) -- bukan cuma diasumsikan sama
    kayak sync karena kodenya keliatan mirip."""
    repo = AsyncArticleRepo(async_db_session)

    a1 = await repo.upsert(url="https://example.com/async-1", title="Async 1", source="Test")
    assert a1.seen_count == 1

    a2 = await repo.upsert(url="https://example.com/async-1", title="Async 1 v2", source="Test")
    assert a2.id == a1.id
    assert a2.seen_count == 2

    fetched = await repo.get_by_url("https://example.com/async-1")
    assert fetched is not None
    assert fetched.title == "Async 1 v2"
