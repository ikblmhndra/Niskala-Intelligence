"""Nquiringminds -- hasil migrasi otomatis dari `ScraperNews/nquiringMindsThreat.py`
(codemod Fase 4, family RSS). Cek `migration_report.json` buat detail
ekstraksi. WAJIB lewat `dry-run` + `verify` sebelum `enable` -- lihat
docs/ADDING_A_SCRAPER.md.
"""

from __future__ import annotations

from cti_scraper.base import ScraperMeta
from cti_scraper.families.rss import RSSScraper
from cti_scraper.schedule import spread


class NquiringMinds(RSSScraper):
    meta = ScraperMeta(
        id="nquiring_minds",
        source="Nquiringminds",
        schedule=spread("16 * * * *", "nquiring_minds"),
        tags=("migrated",),
        legacy_label="NEW ARTICLE FROM NQUIRINGMINDS",
        legacy_script="nquiringMindsThreat",
    )
    feeds = ("https://nquiringminds.com/feed/",)
    date_path = None  # scraper lama pakai waktu-scrape, bukan tanggal artikel asli
