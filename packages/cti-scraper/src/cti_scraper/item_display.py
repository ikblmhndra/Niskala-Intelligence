"""Judul+URL "cukup manusiawi" per tipe `Item` buat `ScraperItem` log
(Fase 9) -- BUKAN kontrak yang scraper author kudu penuhi (beda dari
`sinks.py`'s `sink_for()`, yang wajib didaftarin sebelum tipe itu boleh
di-`yield`). Tabel ini murni best-effort debugging aid ("kenapa scraper
ini nol-item tiba-tiba"), tipe yang gak dikenal jatuh ke fallback generik
`type(item).__name__` -- gak pernah raise.
"""

from __future__ import annotations

from cti_scraper.items import (
    ArticleItem,
    CveItem,
    CvePocItem,
    IocFeedItem,
    Item,
    MalwareTrendItem,
    RansomwareVictimItem,
    TweetItem,
)


def display_title_url(item: Item) -> tuple[str, str]:
    if isinstance(item, ArticleItem):
        return item.title, item.url
    if isinstance(item, TweetItem):
        return item.text[:200], item.url
    if isinstance(item, RansomwareVictimItem):
        return f"{item.group_name}: {item.victim}", item.post_url
    if isinstance(item, CveItem):
        return item.cve_id, item.link or ""
    if isinstance(item, CvePocItem):
        return f"{item.cve_id} POC", item.url
    if isinstance(item, MalwareTrendItem):
        return f"#{item.rank} {item.malware_name}", item.url
    if isinstance(item, IocFeedItem):
        return item.commit_message[:200], item.commit_url
    return type(item).__name__, ""
