"""Intel471 -- hasil migrasi otomatis dari `ScraperNews/intel471Threat.py`
(codemod Fase 4, family XPath runtime="browser"). Cek
`migration_report.json` buat detail ekstraksi. WAJIB lewat `dry-run` +
`verify` sebelum `enable` -- lihat docs/ADDING_A_SCRAPER.md.
"""

from __future__ import annotations

from cti_scraper.base import ScraperMeta
from cti_scraper.families.xpath import XPathScraper
from cti_scraper.schedule import spread


class Intel471(XPathScraper):
    meta = ScraperMeta(
        id="intel471",
        source="Intel471",
        schedule=spread("0 * * * *", "intel471"),
        runtime="browser",
        rate_limit="6/minute",
        max_items=4,
        tags=("migrated",),
        legacy_label="NEW ARTICLE/PAPER FROM INTEL471",
        legacy_script="intel471Threat",
    )
    url = 'https://intel471.com/resources/whitepapers'
    title_xpath = '/html/body/main/div[2]/div/div[2]/a[{i}]/article/div[2]/div[2]/h3'
    link_xpath = '/html/body/main/div[2]/div/div[2]/a[{i}]'
    base_url = "https://www.intel471.com"
