"""Doyensec -- hasil migrasi otomatis dari `ScraperNews/doyensecThreat.py`
(codemod Fase 4, family RSS). Cek `migration_report.json` buat detail
ekstraksi. WAJIB lewat `dry-run` + `verify` sebelum `enable` -- lihat
docs/ADDING_A_SCRAPER.md.
"""

from __future__ import annotations

from cti_scraper.base import ScraperMeta
from cti_scraper.families.rss import RSSScraper
from cti_scraper.schedule import spread


class Doyensec(RSSScraper):
    meta = ScraperMeta(
        id="doyensec",
        source="Doyensec",
        schedule=spread("46 * * * *", "doyensec"),
        tags=("migrated",),
        legacy_label="NEW ARTICLE FROM DOYENSEC",
        legacy_script="doyensecThreat",
    )
    feeds = ('https://blog.doyensec.com/atom.xml',)
    date_path = None  # scraper lama pakai waktu-scrape, bukan tanggal artikel asli
