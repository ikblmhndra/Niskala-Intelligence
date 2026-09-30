"""Sysdig -- hasil migrasi otomatis dari `ScraperNews/sysdigThreat.py`
(codemod Fase 4, family RSS). Cek `migration_report.json` buat detail
ekstraksi. WAJIB lewat `dry-run` + `verify` sebelum `enable` -- lihat
docs/ADDING_A_SCRAPER.md.
"""

from __future__ import annotations

from cti_scraper.base import ScraperMeta
from cti_scraper.families.rss import RSSScraper
from cti_scraper.schedule import spread


class Sysdig(RSSScraper):
    meta = ScraperMeta(
        id="sysdig",
        source="Sysdig",
        schedule=spread("32 * * * *", "sysdig"),
        tags=("migrated",),
        legacy_label="NEW ARTICLE FROM SYSDIG",
        legacy_script="sysdigThreat",
    )
    feeds = ("https://sysdig.com/blog/topic/threat-research/feed/",)
    date_path = None  # scraper lama pakai waktu-scrape, bukan tanggal artikel asli
