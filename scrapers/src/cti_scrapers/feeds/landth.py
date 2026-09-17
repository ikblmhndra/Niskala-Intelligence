"""L&T -- ditulis manual (codemod Fase 4 nolak nge-generate otomatis).
`ScraperNews/landthThreat.py` asli pakai variabel loop `recent_count`
(bukan `i` langsung) buat placeholder XPath -- extractor sengaja gak mau
nebak nama variabel counter (lihat `tools/codemod/extract.py` docstring:
"kenali bentuk KANONIK secara presisi ... JANGAN nebak"), jadi ini
ditinjau & ditulis manual, bukan diakalin di kodemod buat satu file.
Perilakunya sama persis: `recent_count` mulai dari 1, naik 1 tiap
iterasi `range(1, 4)` -- identik `{i}`.
"""

from __future__ import annotations

from cti_scraper.base import ScraperMeta
from cti_scraper.families.xpath import XPathScraper
from cti_scraper.schedule import spread

_CARD = "/html/body/div/div/div[4]/section/div[2]/div[2]/div/div/section/div/article[{i}]"


class Landth(XPathScraper):
    meta = ScraperMeta(
        id="landth",
        source="L&T",
        schedule=spread("16 * * * *", "landth"),
        runtime="light",
        max_items=3,  # scraper lama: range(1, 4) -> 3 kartu
        tags=("migrated",),
        legacy_label="NEW RECENT ARTICLE FROM LANDTH",
        legacy_script="landthThreat",
    )
    url = "https://www.landh.tech/blog/"
    title_xpath = f"{_CARD}/a/section[2]/div[2]/h3/text()"
    link_xpath = f"{_CARD}/a/@href"
    base_url = "https://www.landh.tech"
