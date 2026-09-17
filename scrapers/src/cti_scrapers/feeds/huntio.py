"""Hunt Io -- hasil migrasi otomatis dari `ScraperNews/huntioThreat.py`
(codemod Fase 4, family XPath runtime="browser"). Cek
`migration_report.json` buat detail ekstraksi. WAJIB lewat `dry-run` +
`verify` sebelum `enable` -- lihat docs/ADDING_A_SCRAPER.md.
"""

from __future__ import annotations

from cti_scraper.base import ScraperMeta
from cti_scraper.families.xpath import XPathScraper
from cti_scraper.schedule import spread


class Huntio(XPathScraper):
    meta = ScraperMeta(
        id="huntio",
        source="Hunt Io",
        schedule=spread("16 * * * *", "huntio"),
        runtime="browser",
        rate_limit="6/minute",
        max_items=4,
        tags=("migrated",),
        legacy_label="NEW ARTICLE FROM HUNT IO",
        legacy_script="huntioThreat",
    )
    url = 'https://hunt.io/blog'
    title_xpath = '/html/body/div[1]/div[1]/div[2]/div/div[1]/div[1]/div/div/div[{i}]/div/div/div/div[1]/div[2]/h2/a/text()'
    link_xpath = '/html/body/div[1]/div[1]/div[2]/div/div[1]/div[1]/div/div/div[{i}]/div/div/div/div[1]/div[2]/h2/a/@href'
    base_url = "https://hunt.io"
