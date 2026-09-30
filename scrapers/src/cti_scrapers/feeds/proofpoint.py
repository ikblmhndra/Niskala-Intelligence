"""Proofpoint -- hasil migrasi otomatis dari `ScraperNews/proofpointThreat.py`
(codemod Fase 4, family XPath runtime="browser"). Cek
`migration_report.json` buat detail ekstraksi. WAJIB lewat `dry-run` +
`verify` sebelum `enable` -- lihat docs/ADDING_A_SCRAPER.md.
"""

from __future__ import annotations

from cti_scraper.base import ScraperMeta
from cti_scraper.families.xpath import XPathScraper
from cti_scraper.schedule import spread


class Proofpoint(XPathScraper):
    meta = ScraperMeta(
        id="proofpoint",
        source="Proofpoint",
        schedule=spread("0 * * * *", "proofpoint"),
        runtime="browser",
        rate_limit="6/minute",
        max_items=4,
        tags=("migrated",),
        legacy_label="NEW THREAT INSIGHT ARTICLE FROM PROOFPOINT",
        legacy_script="proofpointThreat",
    )
    url = "https://www.proofpoint.com/us/blog/threat-insight"
    title_xpath = "/html/body/div[2]/div[1]/div[2]/main/section/div/div/div/div/div[5]/div/div[2]/div[1]/div[{i}]/div/div[2]/a[1]/h3"
    link_xpath = "/html/body/div[2]/div[1]/div[2]/main/section/div/div/div/div/div[5]/div/div[2]/div[1]/div[{i}]/div/div[2]/a[1]"
    base_url = "https://www.proofpoint.com"
