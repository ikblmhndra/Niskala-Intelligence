"""Cloudflare -- hasil migrasi otomatis dari `ScraperNews/cloudflareThreat.py`
(codemod Fase 4, family XPath runtime="browser"). Cek
`migration_report.json` buat detail ekstraksi. WAJIB lewat `dry-run` +
`verify` sebelum `enable` -- lihat docs/ADDING_A_SCRAPER.md.
"""

from __future__ import annotations

from cti_scraper.base import ScraperMeta
from cti_scraper.families.xpath import XPathScraper
from cti_scraper.schedule import spread


class Cloudflare(XPathScraper):
    meta = ScraperMeta(
        id="cloudflare",
        source="Cloudflare",
        schedule=spread("1 * * * *", "cloudflare"),
        runtime="browser",
        rate_limit="6/minute",
        max_items=4,
        tags=("migrated",),
        legacy_label="NEW ARTICLE FROM CLOUDFLARE",
        legacy_script="cloudflareThreat",
    )
    url = 'https://www.cloudflare.com/resource-hub/?resourcetype=Report'
    title_xpath = '/html/body/div[1]/div[1]/div/div[4]/div[2]/div/div[3]/div[1]/div[{i}]/div/h4'
    link_xpath = '/html/body/div[1]/div[1]/div/div[4]/div[2]/div/div[3]/div[1]/div[{i}]/div/a'
    base_url = "https://www.cloudflare.com"
