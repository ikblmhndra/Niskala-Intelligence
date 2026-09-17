"""CrowdStrike -- ditulis manual (codemod Fase 4 nolak nge-generate otomatis
karena ada filter di dalam loop). `ScraperNews/crowdstrikeThreat.py` asli
cuma nerima item yang punya `<category>Counter Adversary Operations</category>`
-- filter ini udah dikonfirmasi SAH lewat investigasi Fase 0.5 (bukan bug,
lihat KNOWN_BROKEN.md: feed-nya emang cuma 1 item/hari yang lolos filter).
"""

from __future__ import annotations

from xml.etree.ElementTree import Element

from cti_scraper.base import ScraperMeta
from cti_scraper.families.rss import RSSScraper
from cti_scraper.schedule import spread


class Crowdstrike(RSSScraper):
    meta = ScraperMeta(
        id="crowdstrike",
        source="CrowdStrike",
        schedule=spread("30 * * * *", "crowdstrike"),
        tags=("migrated",),
        legacy_label="NEW ARTICLE FROM CROWDSTRIKE",
        legacy_script="crowdstrikeThreat",
    )
    feeds = ("https://www.crowdstrike.com/en-us/blog/feed",)
    date_path = None  # scraper lama pakai waktu-scrape, bukan tanggal artikel asli
    xml_fixups = (("&ndash;", ""), ("&", "&amp;"))
    html_unescape = True  # feed lama pakai html.unescape() sebelum parse XML

    def _include_item(self, node: Element) -> bool:
        return any(cat.text == "Counter Adversary Operations" for cat in node.findall("category"))
