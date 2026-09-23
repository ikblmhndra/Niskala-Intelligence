"""Snapshot test `routers/tweets.py` -- Fase 7.6 (lanjutan pola pilot
`test_cve_router_snapshot.py`)."""

from __future__ import annotations

import datetime
from collections.abc import Callable

import pytest
from cti_core.db.models.tweet import Tweet
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from syrupy.assertion import SnapshotAssertion
from syrupy.matchers import path_type

pytestmark = pytest.mark.asyncio

_NORMALIZE = path_type(
    {
        r"(.*\.)?id$": (int,),
        r"(.*\.)?fetched_at$": (str,),
    },
    regex=True,
    strict=False,
)


async def _seed_tweet(session: AsyncSession) -> None:
    session.add(
        Tweet(
            tweet_id="1234567890",
            url="https://twitter.com/example/status/1234567890",
            text="APT41 targeting manufacturing sector",
            author_username="threatintel",
            author_name="Threat Intel",
            posted_on=datetime.datetime(2026, 9, 1, tzinfo=datetime.UTC),
            lang="en",
            scan_results={"apac_indicator": True, "mentioned_group": ["Apt41"]},
            confidence_score=80,
        )
    )
    await session.flush()


async def test_tweet_stats(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
    snapshot: SnapshotAssertion,
) -> None:
    await _seed_tweet(api_session)
    resp = await api_client.get("/api/tweets/stats", headers=auth_header())
    assert resp.status_code == 200
    assert resp.json() == snapshot


async def test_list_tweets(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
    snapshot: SnapshotAssertion,
) -> None:
    await _seed_tweet(api_session)
    resp = await api_client.get("/api/tweets", headers=auth_header())
    assert resp.status_code == 200
    assert resp.json() == snapshot(matcher=_NORMALIZE)
