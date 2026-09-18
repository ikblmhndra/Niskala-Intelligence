"""Integration test `AsyncTweetRepo`/`AsyncMonitoredAccountRepo` -- Postgres
REAL (testcontainers). Fase 7.3 (router `tweets`/`monitored_accounts`)."""

from __future__ import annotations

import datetime
from typing import cast

import pytest
from cti_core.db.models.tweet import Tweet
from cti_core.db.repositories.tweet import AsyncMonitoredAccountRepo, AsyncTweetRepo
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio


async def _seed(session: AsyncSession) -> None:
    session.add(
        Tweet(
            tweet_id="1001",
            url="https://x.com/a/status/1001",
            text="APAC ransomware group hits a bank",
            author_username="threatfeed",
            posted_on=datetime.datetime(2026, 9, 10, tzinfo=datetime.UTC),
            scan_results={"apac_indicator": True, "ot_status": False},
            confirmed_incident=True,
        )
    )
    session.add(
        Tweet(
            tweet_id="1002",
            url="https://x.com/b/status/1002",
            text="OT system compromised in Europe",
            author_username="othersource",
            posted_on=datetime.datetime(2026, 9, 12, tzinfo=datetime.UTC),
            scan_results={"apac_indicator": False, "ot_status": True},
            confirmed_incident=False,
        )
    )
    session.add(
        Tweet(
            tweet_id="1003",
            url="https://x.com/a/status/1003",
            text="Unrelated tech announcement",
            author_username="threatfeed",
            posted_on=datetime.datetime(2026, 9, 14, tzinfo=datetime.UTC),
            scan_results={},
            confirmed_incident=False,
        )
    )
    await session.flush()


class TestAsyncTweetRepo:
    async def test_list_filtered_no_filters_returns_all(
        self, async_db_session: AsyncSession
    ) -> None:
        await _seed(async_db_session)
        tweets, total = await AsyncTweetRepo(async_db_session).list_filtered()
        assert total == 3
        # posted_on desc
        assert tweets[0].tweet_id == "1003"

    async def test_list_filtered_by_apac_only(self, async_db_session: AsyncSession) -> None:
        await _seed(async_db_session)
        tweets, total = await AsyncTweetRepo(async_db_session).list_filtered(apac_only=True)
        assert total == 1
        assert tweets[0].tweet_id == "1001"

    async def test_list_filtered_by_ot_only(self, async_db_session: AsyncSession) -> None:
        await _seed(async_db_session)
        tweets, total = await AsyncTweetRepo(async_db_session).list_filtered(ot_only=True)
        assert total == 1
        assert tweets[0].tweet_id == "1002"

    async def test_list_filtered_by_confirmed_only(self, async_db_session: AsyncSession) -> None:
        await _seed(async_db_session)
        tweets, total = await AsyncTweetRepo(async_db_session).list_filtered(confirmed_only=True)
        assert total == 1
        assert tweets[0].tweet_id == "1001"

    async def test_list_filtered_by_author(self, async_db_session: AsyncSession) -> None:
        await _seed(async_db_session)
        _, total = await AsyncTweetRepo(async_db_session).list_filtered(author="threatfeed")
        assert total == 2

    async def test_list_filtered_by_search(self, async_db_session: AsyncSession) -> None:
        await _seed(async_db_session)
        _, total = await AsyncTweetRepo(async_db_session).list_filtered(search="ransomware")
        assert total == 1

    async def test_list_filtered_by_date_range(self, async_db_session: AsyncSession) -> None:
        await _seed(async_db_session)
        _, total = await AsyncTweetRepo(async_db_session).list_filtered(
            posted_on_start=datetime.datetime(2026, 9, 11, tzinfo=datetime.UTC),
            posted_on_end=datetime.datetime(2026, 9, 13, tzinfo=datetime.UTC),
        )
        assert total == 1

    async def test_get_stats_top_authors(self, async_db_session: AsyncSession) -> None:
        await _seed(async_db_session)
        stats = await AsyncTweetRepo(async_db_session).get_stats()
        assert stats["total"] == 3
        rows = cast("list[dict[str, object]]", stats["top_authors"])
        by_author = {row["author"]: row["count"] for row in rows}
        assert by_author["threatfeed"] == 2
        assert by_author["othersource"] == 1

    async def test_get_stats_respects_filters(self, async_db_session: AsyncSession) -> None:
        await _seed(async_db_session)
        stats = await AsyncTweetRepo(async_db_session).get_stats(apac_only=True)
        assert stats["total"] == 1


class TestAsyncMonitoredAccountRepo:
    async def test_create_normalizes_username(self, async_db_session: AsyncSession) -> None:
        repo = AsyncMonitoredAccountRepo(async_db_session)
        account = await repo.create("@ThreatFeed", "Threat Feed", "some notes")
        assert account.username == "threatfeed"
        assert account.display_name == "Threat Feed"
        assert account.active is True

    async def test_create_rejects_duplicate(self, async_db_session: AsyncSession) -> None:
        repo = AsyncMonitoredAccountRepo(async_db_session)
        await repo.create("threatfeed")
        with pytest.raises(ValueError, match="already monitored"):
            await repo.create("@ThreatFeed")

    async def test_list_all_sorted_by_username(self, async_db_session: AsyncSession) -> None:
        repo = AsyncMonitoredAccountRepo(async_db_session)
        await repo.create("zzz")
        await repo.create("aaa")
        accounts = await repo.list_all()
        assert [a.username for a in accounts] == ["aaa", "zzz"]

    async def test_toggle_active(self, async_db_session: AsyncSession) -> None:
        repo = AsyncMonitoredAccountRepo(async_db_session)
        await repo.create("threatfeed")
        assert await repo.toggle("threatfeed", False) is True
        account = await repo.get("threatfeed")
        assert account is not None
        assert account.active is False

    async def test_toggle_missing_returns_false(self, async_db_session: AsyncSession) -> None:
        repo = AsyncMonitoredAccountRepo(async_db_session)
        assert await repo.toggle("ghost", False) is False

    async def test_remove(self, async_db_session: AsyncSession) -> None:
        repo = AsyncMonitoredAccountRepo(async_db_session)
        await repo.create("threatfeed")
        assert await repo.remove("threatfeed") is True
        assert await repo.get("threatfeed") is None
        assert await repo.remove("threatfeed") is False
