"""Port CRUD-baca dari `ScraperNewsWeb/app/routers/tweets.py`. `GET /balance`
(cek kuota API twitterapi.io) SENGAJA gak diport -- passthrough eksternal
doang, gak nyimpen/nge-query data platform, gak genting buat inti."""

from __future__ import annotations

import datetime

from cti_core.db.models.tweet import Tweet
from cti_core.db.repositories.tweet import AsyncTweetRepo
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from cti_api.deps import get_db, require_auth
from cti_api.schemas.tweet import TweetListResponse, TweetOut

router = APIRouter(prefix="/api/tweets", tags=["tweets"], dependencies=[Depends(require_auth)])


def _serialize(t: Tweet) -> TweetOut:
    scan = t.scan_results
    return TweetOut(
        id=t.id,
        tweet_id=t.tweet_id,
        url=t.url,
        text=t.text,
        author_username=t.author_username,
        author_name=t.author_name or "",
        author_avatar=t.author_avatar or "",
        author_followers=t.author_followers or 0,
        posted_on=t.posted_on.isoformat() if t.posted_on else "",
        lang=t.lang or "en",
        media_urls=t.media_urls,
        fetched_at=t.fetched_at.isoformat() if t.fetched_at else "",
        apac_indicator=bool(scan.get("apac_indicator", False)),
        mentioned_group=scan.get("mentioned_group", []),
        mentioned_apac_country=scan.get("mentioned_apac_country", []),
        mentioned_apac_people=scan.get("mentioned_apac_people", []),
        cve_list=scan.get("cve_list", []),
        zero_day_list=scan.get("zero_day_list", []),
        databreach_list=scan.get("databreach_list", []),
        ot_status=bool(scan.get("ot_status", False)),
        report_status=bool(scan.get("report_status", False)),
        confidence=t.confidence_score,
        industries_impacted=t.industries_impacted,
        victim_countries=t.victim_countries,
        actor_countries=t.actor_countries,
        confirmed_incident=t.confirmed_incident,
        incident_confidence=t.incident_confidence,
        incident_indicators=t.incident_indicators,
        victim_name=t.victim_name,
    )


@router.get("/stats")
async def tweet_stats(
    search: str | None = None,
    author: str | None = None,
    lang: str | None = None,
    posted_on_start: datetime.datetime | None = None,
    posted_on_end: datetime.datetime | None = None,
    apac_only: bool = Query(False),
    ot_only: bool = Query(False),
    confirmed_only: bool = Query(False),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    return await AsyncTweetRepo(session).get_stats(
        search=search,
        author=author,
        lang=lang,
        posted_on_start=posted_on_start,
        posted_on_end=posted_on_end,
        apac_only=apac_only,
        ot_only=ot_only,
        confirmed_only=confirmed_only,
    )


@router.get("", response_model=TweetListResponse)
async def list_tweets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    author: str | None = None,
    lang: str | None = None,
    posted_on_start: datetime.datetime | None = None,
    posted_on_end: datetime.datetime | None = None,
    apac_only: bool = Query(False),
    ot_only: bool = Query(False),
    confirmed_only: bool = Query(False),
    session: AsyncSession = Depends(get_db),
) -> TweetListResponse:
    tweets, total = await AsyncTweetRepo(session).list_filtered(
        page=page,
        page_size=page_size,
        search=search,
        author=author,
        lang=lang,
        posted_on_start=posted_on_start,
        posted_on_end=posted_on_end,
        apac_only=apac_only,
        ot_only=ot_only,
        confirmed_only=confirmed_only,
    )
    return TweetListResponse(
        tweets=[_serialize(t) for t in tweets], total=total, page=page, page_size=page_size
    )
