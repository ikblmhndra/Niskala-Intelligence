"""Cis -- hasil migrasi otomatis dari `ScraperNews/cisThreat.py`
(codemod Fase 4, family XPath runtime="browser"). Cek
`migration_report.json` buat detail ekstraksi. WAJIB lewat `dry-run` +
`verify` sebelum `enable` -- lihat docs/ADDING_A_SCRAPER.md.
"""

from __future__ import annotations

from cti_scraper.base import ScraperMeta
from cti_scraper.families.xpath import XPathScraper
from cti_scraper.schedule import spread


class Cis(XPathScraper):
    meta = ScraperMeta(
        id="cis",
        source="Cis",
        schedule=spread("30 * * * *", "cis"),
        runtime="browser",
        rate_limit="6/minute",
        max_items=4,
        tags=("migrated",),
        legacy_label="NEW ARTICLE FROM CIS",
        legacy_script="cisThreat",
    )
    url = "https://cisecurity.org/advisory"
    title_xpath = "/html/body/div[2]/div[2]/main/div[2]/div[2]/div[2]/div[1]/div/div[{i}]/div[2]/div[2]/a/text()"
    link_xpath = "/html/body/div[2]/div[2]/main/div[2]/div[2]/div[2]/div[1]/div/div[{i}]/div[2]/div[2]/a/@href"
    base_url = "https://cisecurity.org"
