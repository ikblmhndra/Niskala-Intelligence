"""Queue scrape mana buat scraper mana -- `ScraperMeta.runtime` (Fase 3)
udah didokumentasikan bakal nentuin ini ("router Celery (runtime -> queue)
-- lihat base.py), plan §4 nyebut 3 queue scrape (`scrape.rss`,
`scrape.browser`, `scrape.api`) tapi framework cuma punya 2 nilai
`runtime` (light/browser) -- gak ada field "api" eksplisit.

Jalan keluarnya: `runtime="browser"` -> `scrape.browser` (butuh image
Chromium/Playwright, lihat plan §9/§10 image terpisah). `runtime="light"`
dipecah lagi pake `credential` sebagai proxy "ini scraper API terautentikasi
(GitHub/NVD/Twitter dst), bukan RSS/XPath biasa" -- soalnya scraper
ber-credential emang secara konsisten yang paling butuh rate limit ketat/
isolasi worker terpisah (github_poc_monitor.py Search API 30/menit vs RSS
biasa 20/menit default), bukan asumsi sembarangan."""

from __future__ import annotations

from cti_scraper.base import ScraperMeta

QUEUE_BROWSER = "scrape.browser"
QUEUE_API = "scrape.api"
QUEUE_RSS = "scrape.rss"
QUEUE_ENRICH = "enrich"
QUEUE_NOTIFY = "notify"
QUEUE_MAINTENANCE = "maintenance"

ALL_SCRAPE_QUEUES = (QUEUE_RSS, QUEUE_API, QUEUE_BROWSER)


def queue_for(meta: ScraperMeta) -> str:
    if meta.runtime == "browser":
        return QUEUE_BROWSER
    if meta.credential is not None:
        return QUEUE_API
    return QUEUE_RSS
