"""SentinelOne Labs -- ditulis manual (codemod Fase 4 nolak nge-generate
otomatis karena ada filter di dalam loop). `ScraperNews/sentinelThreat.py`
asli cuma nerima item yang punya kategori "From the Front Lines" atau
"The Good, the Bad and the Ugly" -- TAPI ada kuirk: `skip_status` di-init
`False` dan CUMA di-set di dalam `for cat in item.findall('category')`,
jadi item yang gak punya `<category>` SAMA SEKALI (loop-nya gak pernah
jalan) otomatis LOLOS filter -- beda dari `bleepcomp.py`/`crowdstrike.py`
yang punya bentuk sama tapi default-nya "exclude". Diverifikasi lewat
fixture (item "Agents at Large..." gak punya `<category>` tapi tetap ada
di expected_items) -- kuirk ini SENGAJA dipertahankan, bukan diperbaiki,
karena itu perilaku produksi yang sebenarnya, bukan crash/bug fatal kayak
yang tercatat di KNOWN_BROKEN.md.
"""

from __future__ import annotations

from xml.etree.ElementTree import Element

from cti_scraper.base import ScraperMeta
from cti_scraper.families.rss import RSSScraper
from cti_scraper.schedule import spread

_ALLOWED_CATEGORIES = {"From the Front Lines", "The Good, the Bad and the Ugly"}


class Sentinel(RSSScraper):
    meta = ScraperMeta(
        id="sentinel",
        source="SentinelOne Labs",
        schedule=spread("30 * * * *", "sentinel"),
        tags=("migrated",),
        legacy_label="NEW ARTICLE FROM SENTINELONE",
        legacy_script="sentinelThreat",
    )
    feeds = ("https://www.sentinelone.com/labs/feed/",)
    date_path = None  # scraper lama pakai waktu-scrape, bukan tanggal artikel asli

    def _include_item(self, node: Element) -> bool:
        categories = node.findall("category")
        if not categories:
            return True
        return any(cat.text in _ALLOWED_CATEGORIES for cat in categories)
