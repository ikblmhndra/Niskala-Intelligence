"""Sans -- hasil migrasi otomatis dari `ScraperNews/sansThreat.py`
(codemod Fase 4, family XPath runtime="browser"). Cek
`migration_report.json` buat detail ekstraksi. WAJIB lewat `dry-run` +
`verify` sebelum `enable` -- lihat docs/ADDING_A_SCRAPER.md.
"""

from __future__ import annotations

from cti_scraper.base import ScraperMeta
from cti_scraper.families.xpath import XPathScraper
from cti_scraper.schedule import spread


class Sans(XPathScraper):
    meta = ScraperMeta(
        id="sans",
        source="Sans",
        schedule=spread("30 * * * *", "sans"),
        runtime="browser",
        rate_limit="6/minute",
        max_items=4,
        tags=("migrated",),
        legacy_label="NEW ARTICLE FROM SANS",
        legacy_script="sansThreat",
    )
    url = "https://www.sans.org/white-papers/?focus-area=cloud-security,cyber-defense,cyber-security-it-essentials,cybersecurity-insights,devsecops,digital-forensics,incident-response-threat-hunting,purple-team,security-awareness"
    title_xpath = "/html/body/div[2]/div/div/main/div/div[2]/div[2]/ul/li[{i}]/div/a/text()"
    link_xpath = "/html/body/div[2]/div/div/main/div/div[2]/div[2]/ul/li[{i}]/div/a/@href"
    base_url = "https://www.sans.org"
