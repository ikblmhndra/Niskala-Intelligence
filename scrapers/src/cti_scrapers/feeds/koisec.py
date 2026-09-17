"""Koi Security -- hasil migrasi otomatis dari `ScraperNews/koisecThreat.py`
(codemod Fase 4, family XPath runtime="browser"). Cek
`migration_report.json` buat detail ekstraksi. WAJIB lewat `dry-run` +
`verify` sebelum `enable` -- lihat docs/ADDING_A_SCRAPER.md.
"""

from __future__ import annotations

from cti_scraper.base import ScraperMeta
from cti_scraper.families.xpath import XPathScraper
from cti_scraper.schedule import spread


class Koisec(XPathScraper):
    meta = ScraperMeta(
        id="koisec",
        source="Koi Security",
        schedule=spread("17 * * * *", "koisec"),
        runtime="browser",
        rate_limit="6/minute",
        max_items=4,
        tags=("migrated",),
        legacy_label="NEW ARTICLE FROM KOI SECURITY",
        legacy_script="koisecThreat",
    )
    url = 'https://www.koi.security/blog'
    title_xpath = '/html/body/div/div[4]/main/section/div/div/div/div[3]/div/div[{i}]/div[1]/div[1]/h3'
    link_xpath = '/html/body/div/div[4]/main/section/div/div/div/div[3]/div/div[{i}]/a'
    base_url = "https://www.koi.ai/blog"
