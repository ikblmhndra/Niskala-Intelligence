"""Name -- hasil migrasi otomatis dari `ScraperNews/blackberryThreat.py`
(codemod Fase 4, family XPath runtime="browser"). Cek
`migration_report.json` buat detail ekstraksi. WAJIB lewat `dry-run` +
`verify` sebelum `enable` -- lihat docs/ADDING_A_SCRAPER.md.
"""

from __future__ import annotations

from cti_scraper.base import ScraperMeta
from cti_scraper.families.xpath import XPathScraper
from cti_scraper.schedule import spread


class Blackberry(XPathScraper):
    meta = ScraperMeta(
        id="blackberry",
        source="Name",
        schedule=spread("0 * * * *", "blackberry"),
        runtime="browser",
        rate_limit="6/minute",
        max_items=4,
        tags=("migrated",),
        legacy_label="NEW ARTICLE FROM NAME",
        legacy_script="blackberryThreat",
    )
    url = 'https://blogs.blackberry.com/en/category/research-and-intelligence'
    title_xpath = '/html/body/main/div[2]/section/div/div[2]/div[1]/div[{i}]/div/div/div/a[2]/text()'
    link_xpath = '/html/body/main/div[2]/section/div/div[2]/div[1]/div[{i}]/div/div/div/a[2]/@href'
