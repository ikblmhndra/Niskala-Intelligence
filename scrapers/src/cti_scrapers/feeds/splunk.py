"""Splunk -- hasil migrasi otomatis dari `ScraperNews/splunkThreat.py`
(codemod Fase 4, family XPath runtime="browser"). Cek
`migration_report.json` buat detail ekstraksi. WAJIB lewat `dry-run` +
`verify` sebelum `enable` -- lihat docs/ADDING_A_SCRAPER.md.
"""

from __future__ import annotations

from cti_scraper.base import ScraperMeta
from cti_scraper.families.xpath import XPathScraper
from cti_scraper.schedule import spread


class Splunk(XPathScraper):
    meta = ScraperMeta(
        id="splunk",
        source="Splunk",
        schedule=spread("45 * * * *", "splunk"),
        runtime="browser",
        rate_limit="6/minute",
        max_items=3,
        tags=("migrated",),
        legacy_label="NEW RECENT ARTICLE FROM SPLUNK",
        legacy_script="splunkThreat",
    )
    url = "https://www.splunk.com/en_us/blog/security.html"
    title_xpath = "/html/body/main/div[2]/div[2]/div/div/div[{i}]/div[2]/h3/a/text()"
    link_xpath = "/html/body/main/div[2]/div[2]/div/div/div[{i}]/div[2]/h3/a/@href"
    base_url = "https://www.splunk.com"
