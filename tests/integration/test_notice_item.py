"""`NoticeItem` (Fase 10.E) -- pesan Telegram murni tanpa enrichment.

Dua hal yang dikunci: (1) sink-nya benar (teks vs dokumen, batas panjang
Telegram, nama file aman), dan (2) semantik at-least-once lewat `Runner`
beneran: kegagalan kirim TIDAK boleh menandai item "sudah terlihat" -- itu
kebalikan dari `send_alert_*` lama yang menelan exception, dan notice-nya
hilang selamanya. Telegram di-patch; DB dan Runner asli.
"""

from __future__ import annotations

import datetime
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from cti_core.db.models.scraper import ScraperItem, ScraperSeen
from cti_scraper.base import BaseScraper, ScrapeContext, ScraperMeta
from cti_scraper.item_display import display_title_url
from cti_scraper.items import Item, NoticeItem
from cti_scraper.runner import Runner
from sqlalchemy import select
from sqlalchemy.orm import Session

SID = "test-notice"


def notice(n: int, **over: object) -> NoticeItem:
    base = {
        "topic": "apt",
        "text": f"=== <b>NOTICE {n}</b> ===\nisi {n}",
        "key": f"k{n}",
        "posted_on": datetime.date(2026, 9, n) if n <= 28 else None,
    }
    return NoticeItem(**{**base, **over})  # type: ignore[arg-type]


class Telegram:
    """Perekam pengganti `cti_alerts.telegram.send_alert/send_file`."""

    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []
        self.files: list[tuple[str, str, str, str]] = []  # topic, nama, isi, caption
        self.fail = False

    def send_alert(self, topic: str, msg: str, **_kw: object) -> None:
        if self.fail:
            raise ConnectionError("telegram down")
        self.messages.append((topic, msg))

    def send_file(self, topic: str, path: str, caption: str, **_kw: object) -> None:
        if self.fail:
            raise ConnectionError("telegram down")
        p = Path(path)
        self.files.append((topic, p.name, p.read_text(encoding="utf-8"), caption))


@pytest.fixture
def telegram(monkeypatch: pytest.MonkeyPatch) -> Telegram:
    tg = Telegram()
    monkeypatch.setattr("cti_alerts.telegram.send_alert", tg.send_alert)
    monkeypatch.setattr("cti_alerts.telegram.send_file", tg.send_file)
    return tg


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
        meta = ScraperMeta(id=SID, source="Test", schedule="0 * * * *", max_items=50)

        def fetch(self, ctx: ScrapeContext) -> Iterator[Item]:
            yield from feed()

    return _Scraper


def sink(item: NoticeItem) -> None:
    from cti_scraper.sinks import dispatch

    dispatch(item, ScraperMeta(id=SID, source="Test", schedule="0 * * * *"), None)  # type: ignore[arg-type]


# --- sink ----------------------------------------------------------------------


def test_text_notice_goes_to_its_topic(telegram: Telegram) -> None:
    sink(notice(1))

    assert telegram.messages == [("apt", "=== <b>NOTICE 1</b> ===\nisi 1")]
    assert telegram.files == []


def test_attachment_is_sent_as_a_document_with_the_text_as_caption(telegram: Telegram) -> None:
    sink(notice(1, attachment_name="report.txt", attachment_text="baris 1\nbaris 2"))

    assert telegram.files == [
        ("apt", "report.txt", "baris 1\nbaris 2", "=== <b>NOTICE 1</b> ===\nisi 1")
    ]
    assert telegram.messages == []


def test_attachment_name_cannot_escape_the_temp_directory(telegram: Telegram) -> None:
    sink(notice(1, attachment_name="../../etc/evil.txt", attachment_text="x"))

    assert telegram.files[0][1] == "evil.txt"


def test_caption_over_telegram_limit_becomes_a_separate_message(telegram: Telegram) -> None:
    long_text = "=== <b>PANJANG</b> ===\n" + "x" * 1500  # > 1024, < 4096

    sink(notice(1, text=long_text, attachment_name="p.txt", attachment_text="patch"))

    assert telegram.messages == [("apt", long_text)]
    assert telegram.files == [("apt", "p.txt", "patch", "")]


def test_text_over_telegram_message_limit_fails_loudly_and_sends_nothing(
    telegram: Telegram,
) -> None:
    with pytest.raises(ValueError, match="batas Telegram"):
        sink(notice(1, text="x" * 4097))

    assert telegram.messages == [] and telegram.files == []


# --- display ---------------------------------------------------------------------


def test_display_title_strips_html_from_the_first_line() -> None:
    assert display_title_url(notice(1)) == ("NOTICE 1", "")
    assert display_title_url(notice(1, title="Judul eksplisit", url="https://x/y")) == (
        "Judul eksplisit",
        "https://x/y",
    )


# --- lewat Runner: at-least-once ------------------------------------------------------


def seen_count(session: Session) -> int:
    session.expire_all()
    return len(session.scalars(select(ScraperSeen).where(ScraperSeen.scraper_id == SID)).all())


def test_delivered_once_and_duplicates_are_dropped_on_the_next_run(
    session: Session, telegram: Telegram
) -> None:
    feed = [notice(1), notice(2)]
    scraper = make_scraper(lambda: list(feed))
    Runner(scraper, session=session, cold_start_max_items=99).execute()

    second = Runner(scraper, session=session, cold_start_max_items=99).execute()

    assert len(telegram.messages) == 2
    assert second.items_new == 0 and second.items_dropped == 2


def test_failed_delivery_is_retried_next_run_instead_of_being_lost(
    session: Session, telegram: Telegram
) -> None:
    """INTI: Telegram mati waktu run -> notice TIDAK boleh ditandai `done`."""
    scraper = make_scraper(lambda: [notice(1)])
    telegram.fail = True
    first = Runner(scraper, session=session, cold_start_max_items=99).execute()

    assert first.items_failed == 1 and first.items_new == 0
    assert seen_count(session) == 0  # lease dilepas -- bukan "sudah terlihat"

    telegram.fail = False
    second = Runner(scraper, session=session, cold_start_max_items=99).execute()

    assert second.items_new == 1 and len(telegram.messages) == 1  # akhirnya terkirim


def test_cold_scraper_caps_notices_like_articles(session: Session, telegram: Telegram) -> None:
    """Notice langsung ke channel, jadi run pertama scraper baru gak boleh
    ngebanjirin: cuma N terbaru (`posted_on`) yang dikirim, sisanya ditandai
    seen tanpa dikirim."""
    scraper = make_scraper(lambda: [notice(n) for n in range(1, 7)])  # tanggal 1..6

    result = Runner(scraper, session=session, cold_start_max_items=2).execute()

    assert result.items_new == 2
    assert sorted(m[1].split("\n")[0] for m in telegram.messages) == [
        "=== <b>NOTICE 5</b> ===",
        "=== <b>NOTICE 6</b> ===",
    ]
    assert seen_count(session) == 6  # yang kena cap gak muncul lagi
    logged = {
        r.reason for r in session.scalars(select(ScraperItem).where(ScraperItem.scraper_id == SID))
    }
    assert "cold_start_cap" in logged
