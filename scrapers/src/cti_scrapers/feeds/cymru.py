"""Cymru -- hasil migrasi otomatis dari `ScraperNews/cymruThreat.py`
(codemod Fase 4, family XPath runtime="browser"). Cek
`migration_report.json` buat detail ekstraksi. WAJIB lewat `dry-run` +
`verify` sebelum `enable` -- lihat docs/ADDING_A_SCRAPER.md.
"""

from __future__ import annotations

from cti_scraper.base import ScraperMeta
from cti_scraper.families.xpath import XPathScraper
from cti_scraper.schedule import spread


class Cymru(XPathScraper):
    meta = ScraperMeta(
        id="cymru",
        source="Cymru",
        schedule=spread("47 * * * *", "cymru"),
        runtime="browser",
        rate_limit="6/minute",
        max_items=4,
        tags=("migrated",),
        legacy_label="NEW ARTICLE FROM CYMRU",
        legacy_script="cymruThreat",
    )
    url = 'https://www.team-cymru.com/categories/threat-research'
    title_xpath = '/html/body/main/section[2]/div/div/div/div/div[2]/div/div/div[{i}]/div/div/a/h2'
    link_xpath = '/html/body/main/section[2]/div/div/div/div/div[2]/div/div/div[{i}]/div/div/a'
    base_url = "https://www.team-cymru.com"
