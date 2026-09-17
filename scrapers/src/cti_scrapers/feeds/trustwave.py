"""Trustwave -- hasil migrasi otomatis dari `ScraperNews/trustwaveThreat.py`
(codemod Fase 4, family RSS). Cek `migration_report.json` buat detail
ekstraksi. WAJIB lewat `dry-run` + `verify` sebelum `enable` -- lihat
docs/ADDING_A_SCRAPER.md.
"""

from __future__ import annotations

from cti_scraper.base import ScraperMeta
from cti_scraper.families.rss import RSSScraper
from cti_scraper.schedule import spread


class Trustwave(RSSScraper):
    meta = ScraperMeta(
        id="trustwave",
        source="Trustwave",
        schedule=spread("31 * * * *", "trustwave"),
        tags=("migrated",),
        legacy_label="NEW ARTICLE FROM TRUSTWAVE",
        legacy_script="trustwaveThreat",
    )
    feeds = ('https://www.trustwave.com/en-us/resources/blogs/spiderlabs-blog/rss.xml',)
    date_path = None  # scraper lama pakai waktu-scrape, bukan tanggal artikel asli
