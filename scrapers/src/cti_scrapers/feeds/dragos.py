"""Dragos -- hasil migrasi otomatis dari `ScraperNews/dragosThreat.py`
(codemod Fase 4, family XPath runtime="browser"). Cek
`migration_report.json` buat detail ekstraksi. WAJIB lewat `dry-run` +
`verify` sebelum `enable` -- lihat docs/ADDING_A_SCRAPER.md.
"""

from __future__ import annotations

from cti_scraper.base import ScraperMeta
from cti_scraper.families.xpath import XPathScraper
from cti_scraper.schedule import spread


class Dragos(XPathScraper):
    meta = ScraperMeta(
        id="dragos",
        source="Dragos",
        schedule=spread("1 * * * *", "dragos"),
        runtime="browser",
        rate_limit="6/minute",
        max_items=4,
        tags=("migrated",),
        legacy_label="NEW ARTICLE FROM DRAGOS",
        legacy_script="dragosThreat",
    )
    url = "https://www.dragos.com/blog/?_block_blog_posts_topics=compliance%2Cransomware%2Cresearch%2Cthreats%2Cyear-in-review"
    title_xpath = "/html/body/main/article/div/div/div[2]/div/div[5]/div/article[{i}]/h5/a/text()"
    link_xpath = "/html/body/main/article/div/div/div[2]/div/div[5]/div/article[{i}]/h5/a/@href"
