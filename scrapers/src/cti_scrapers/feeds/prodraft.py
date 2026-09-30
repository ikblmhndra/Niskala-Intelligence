"""Prodaft -- hasil migrasi otomatis dari `ScraperNews/prodraftThreat.py`
(codemod Fase 4, family XPath runtime="browser"). Cek
`migration_report.json` buat detail ekstraksi. WAJIB lewat `dry-run` +
`verify` sebelum `enable` -- lihat docs/ADDING_A_SCRAPER.md.
"""

from __future__ import annotations

from cti_scraper.base import ScraperMeta
from cti_scraper.families.xpath import XPathScraper
from cti_scraper.schedule import spread


class Prodraft(XPathScraper):
    meta = ScraperMeta(
        id="prodraft",
        source="Prodaft",
        schedule=spread("45 * * * *", "prodraft"),
        runtime="browser",
        rate_limit="6/minute",
        max_items=4,
        tags=("migrated",),
        legacy_label="NEW ARTICLE FROM PRODAFT",
        legacy_script="prodraftThreat",
    )
    url = "https://prodaft.com/blogs"
    title_xpath = "/html/body/main/div[2]/section[2]/div[2]/div[{i}]/div[1]/h4/text()"
    link_xpath = "/html/body/main/div[2]/section[2]/div[2]/div[{i}]/div[1]/h4/@href"
