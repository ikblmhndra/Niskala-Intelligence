"""Aquasec -- hasil migrasi otomatis dari `ScraperNews/aquasecThreat.py`
(codemod Fase 4, family XPath runtime="browser"). Cek
`migration_report.json` buat detail ekstraksi. WAJIB lewat `dry-run` +
`verify` sebelum `enable` -- lihat docs/ADDING_A_SCRAPER.md.
"""

from __future__ import annotations

from cti_scraper.base import ScraperMeta
from cti_scraper.families.xpath import XPathScraper
from cti_scraper.schedule import spread


class Aquasec(XPathScraper):
    meta = ScraperMeta(
        id="aquasec",
        source="Aquasec",
        schedule=spread("45 * * * *", "aquasec"),
        runtime="browser",
        rate_limit="6/minute",
        max_items=4,
        tags=("migrated",),
        legacy_label="NEW ARTICLE FROM AQUASEC",
        legacy_script="aquasecThreat",
    )
    url = 'https://www.aquasec.com/blog/'
    title_xpath = '/html/body/div/div[2]/div[1]/div/div[4]/div/div/div[{i}]/a/div[1]/div/div/div[2]'
    link_xpath = '/html/body/div/div[2]/div[1]/div/div[4]/div/div/div[{i}]/a'
