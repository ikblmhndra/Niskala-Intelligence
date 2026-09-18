"""Adaptasi dari `ScraperNewsWeb/app/models/tweet.py`. `apac_indicator`/
`mentioned_group`/dst (field enrichment lama) sekarang di dalam
`scan_results` JSONB -- dipecah ke field top-level di sini biar response
shape API gak berubah drastis (frontend Fase 8 nanti gak perlu tau field
mana yang pindah representasi)."""

from __future__ import annotations

from pydantic import BaseModel


class TweetOut(BaseModel):
    id: int
    tweet_id: str
    url: str
    text: str
    author_username: str
    author_name: str = ""
    author_avatar: str = ""
    author_followers: int = 0
    posted_on: str = ""
    lang: str = "en"
    media_urls: list[str] = []
    fetched_at: str = ""
    apac_indicator: bool = False
    mentioned_group: list[str] = []
    mentioned_apac_country: list[str] = []
    mentioned_apac_people: list[str] = []
    cve_list: list[str] = []
    zero_day_list: list[str] = []
    databreach_list: list[str] = []
    ot_status: bool = False
    report_status: bool = False
    confidence: int | None = None
    industries_impacted: list[str] = []
    victim_countries: list[str] = []
    actor_countries: list[str] = []
    confirmed_incident: bool = False
    incident_confidence: int | None = None
    incident_indicators: list[str] = []
    victim_name: str | None = None


class TweetListResponse(BaseModel):
    tweets: list[TweetOut]
    total: int
    page: int
    page_size: int


class MonitoredAccountOut(BaseModel):
    id: int
    username: str
    display_name: str = ""
    notes: str = ""
    active: bool = True
    added_at: str = ""


class AddAccountRequest(BaseModel):
    username: str
    display_name: str = ""
    notes: str = ""


class ToggleRequest(BaseModel):
    active: bool
