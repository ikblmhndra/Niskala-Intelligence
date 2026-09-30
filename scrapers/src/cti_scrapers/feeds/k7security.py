"""K7 Security -- hasil migrasi otomatis dari `ScraperNews/k7securityThreat.py`
(codemod Fase 4, family XPath runtime="browser"). Cek
`migration_report.json` buat detail ekstraksi. WAJIB lewat `dry-run` +
`verify` sebelum `enable` -- lihat docs/ADDING_A_SCRAPER.md.
"""

from __future__ import annotations

from cti_scraper.base import ScraperMeta
from cti_scraper.families.xpath import XPathScraper
from cti_scraper.schedule import spread


class K7security(XPathScraper):
    meta = ScraperMeta(
        id="k7security",
        source="K7 Security",
        schedule=spread("1 * * * *", "k7security"),
        runtime="browser",
        rate_limit="6/minute",
        max_items=4,
        tags=("migrated",),
        legacy_label="NEW ARTICLE FROM K7 SECURITY",
        legacy_script="k7securityThreat",
    )
    url = "https://www.k7computing.com/in/blog"
    title_xpath = "/html/body/div[3]/div[3]/div[1]/div[3]/div/div/div[1]/div[1]/a[{i}]/div[1]/h2"
    link_xpath = "/html/body/div[3]/div[3]/div[1]/div[3]/div/div/div[1]/div[1]/a[{i}]"
