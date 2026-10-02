"""Adaptasi dari `ScraperNewsWeb/app/models/article.py` -- `id` sekarang
`int` (Postgres bigint autoincrement), BUKAN `str` (Mongo ObjectId hex).
`iocs` SENGAJA selalu `{}` buat sekarang -- linkage artikel<->IOC belum
diport (router `iocs.py`, nyusul terpisah), placeholder daripada nebak
bentuknya sekarang."""

from __future__ import annotations

from pydantic import BaseModel


class TTP(BaseModel):
    id: str
    name: str


class ArticleOut(BaseModel):
    id: int
    year: int = 0
    month: str = ""
    week: str = ""
    title: str = ""
    url: str = ""
    posted_on: str = ""
    source: str = ""
    impacted_industries: list[str] = []
    mentioned_countries: list[str] = []
    victim_countries: list[str] = []
    actor_countries: list[str] = []
    threat_actors: list[str] = []
    ttps: list[TTP] = []
    news_type: str = ""
    confidence_score: int | None = None
    iocs: dict[str, object] = {}


class FilterOptions(BaseModel):
    industries: list[str]
    countries: list[str]
    sources: list[str]
    news_types: list[str]
    threat_actors: list[str]
    date_range: dict[str, str]


class ArticleListResponse(BaseModel):
    articles: list[ArticleOut]
    total: int
    page: int
    page_size: int


class TopItem(BaseModel):
    name: str
    count: int


class TimelinePoint(BaseModel):
    date: str
    count: int


class DashboardStats(BaseModel):
    total_articles: int
    total_sources: int
    total_countries: int
    total_threat_actors: int
    top_countries: list[TopItem]
    # Semua negara (bukan cuma top-10) -- dipakai peta dunia di dashboard.
    country_counts: list[TopItem]
    top_sources: list[TopItem]
    top_threat_actors: list[TopItem]
    top_industries: list[TopItem]
    top_ttps: list[TopItem]
    by_news_type: list[TopItem]
    timeline: list[TimelinePoint]
