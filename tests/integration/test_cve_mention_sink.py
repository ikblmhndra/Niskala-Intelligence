"""`CveMentionItem` -> `cve_mentions` lewat `Runner` (Fase 10.E, `trending_cve`)."""

from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest
from cti_core.db.models.report_state import SCOPE_NEWS, SCOPE_TWEET
from cti_core.db.repositories.report_state import CveMentionRepo
from cti_scraper.base import BaseScraper, ScrapeContext, ScraperMeta
from cti_scraper.item_display import display_title_url
from cti_scraper.items import CveMentionItem, Item
from cti_scraper.runner import Runner
from sqlalchemy.orm import Session

SID = "test-cve-mention"


@pytest.fixture
def session(_migrated_schema: None) -> Iterator[Session]:
    from cti_core.db.engine import get_sync_engine

    connection = get_sync_engine().connect()
    connection.begin()
    s = Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
    try:
        yield s
    finally:
        s.close()
        connection.rollback()
        connection.close()


def make_scraper(feed: Callable[[], list[Item]]) -> type[BaseScraper]:
    class _Scraper(BaseScraper):
        __abstract__ = True
        meta = ScraperMeta(id=SID, source="Test", schedule="*/15 * * * *", max_items=50)

        def fetch(self, ctx: ScrapeContext) -> Iterator[Item]:
            yield from feed()

    return _Scraper


def counts(session: Session, scope: str) -> dict[str, int]:
    return {m.cve_id: m.counter for m in CveMentionRepo(session).top(scope, limit=100)}


def test_each_tweet_bumps_the_tweet_scope_counters(session: Session) -> None:
    feed = [
        CveMentionItem(tweet_id="1", cve_ids=["CVE-2026-0001", "CVE-2026-0002"]),
        CveMentionItem(tweet_id="2", cve_ids=["CVE-2026-0001"]),
    ]

    result = Runner(
        make_scraper(lambda: list(feed)), session=session, cold_start_max_items=99
    ).execute()

    assert result.items_new == 2
    assert counts(session, SCOPE_TWEET) == {"CVE-2026-0001": 2, "CVE-2026-0002": 1}
    assert counts(session, SCOPE_NEWS) == {}  # scope artikel tidak tersentuh


def test_the_same_tweet_in_the_next_search_window_is_not_counted_twice(session: Session) -> None:
    """Pengganti kursor `since_id` skrip lama: jendela pencarian saling tumpang
    tindih, dedup id tweet yang mencegah hitungan ganda."""
    scraper = make_scraper(lambda: [CveMentionItem(tweet_id="1", cve_ids=["CVE-2026-0001"])])

    Runner(scraper, session=session, cold_start_max_items=99).execute()
    second = Runner(scraper, session=session, cold_start_max_items=99).execute()

    assert second.items_new == 0 and second.items_dropped == 1
    assert counts(session, SCOPE_TWEET) == {"CVE-2026-0001": 1}


def test_display_lists_the_tweet_and_its_cves() -> None:
    item = CveMentionItem(tweet_id="9", cve_ids=["CVE-2026-1", "CVE-2026-2"], url="https://x/9")

    assert display_title_url(item) == ("tweet 9: CVE-2026-1, CVE-2026-2", "https://x/9")
