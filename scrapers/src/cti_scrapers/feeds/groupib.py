"""Group Ib -- hasil migrasi otomatis dari `ScraperNews/groupibThreat.py`
(codemod Fase 4, family XPath runtime="browser"). Cek
`migration_report.json` buat detail ekstraksi. WAJIB lewat `dry-run` +
`verify` sebelum `enable` -- lihat docs/ADDING_A_SCRAPER.md.
"""

from __future__ import annotations

from cti_scraper.base import ScraperMeta
from cti_scraper.families.xpath import XPathScraper
from cti_scraper.schedule import spread


class Groupib(XPathScraper):
    meta = ScraperMeta(
        id="groupib",
        source="Group Ib",
        schedule=spread("15 * * * *", "groupib"),
        runtime="browser",
        rate_limit="6/minute",
        max_items=4,
        tags=("migrated",),
        legacy_label="NEW ARTICLE FROM GROUP IB",
        legacy_script="groupibThreat",
    )
    url = 'https://www.group-ib.com/blog/'
    title_xpath = '/html/body/div[4]/div/div/div[2]/div/a[{i}]/div[2]/div[2]'
    link_xpath = '/html/body/div[4]/div/div/div[2]/div/a[{i}]'
