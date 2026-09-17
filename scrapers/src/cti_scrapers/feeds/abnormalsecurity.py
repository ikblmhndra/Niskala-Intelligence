"""Abnormal Security -- hasil migrasi otomatis dari `ScraperNews/abnormalsecurityThreat.py`
(codemod Fase 4, family XPath runtime="browser"). Cek
`migration_report.json` buat detail ekstraksi. WAJIB lewat `dry-run` +
`verify` sebelum `enable` -- lihat docs/ADDING_A_SCRAPER.md.
"""

from __future__ import annotations

from cti_scraper.base import ScraperMeta
from cti_scraper.families.xpath import XPathScraper
from cti_scraper.schedule import spread


class Abnormalsecurity(XPathScraper):
    meta = ScraperMeta(
        id="abnormalsecurity",
        source="Abnormal Security",
        schedule=spread("15 * * * *", "abnormalsecurity"),
        runtime="browser",
        rate_limit="6/minute",
        max_items=4,
        tags=("migrated",),
        legacy_label="NEW ARTICLE FROM ABNORMAL SECURITY",
        legacy_script="abnormalsecurityThreat",
    )
    url = 'https://abnormal.ai/blog/category/threat-intel'
    title_xpath = '/html/body/div[2]/div[2]/div/main/div[3]/div/div/div[{i}]/div/div[2]/div[1]/div/div/a/span'
    link_xpath = '/html/body/div[2]/div[2]/div/main/div[3]/div/div/div[{i}]/div/div[2]/div[1]/div/div/a'
    base_url = "https://abnormal.ai"
