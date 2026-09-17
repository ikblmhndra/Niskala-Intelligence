"""Huntress -- ditulis manual (codemod Fase 4 nolak nge-generate otomatis).
`ScraperNews/huntressThreat.py` asli gak pakai XPath ber-indeks (`{i}`) sama
sekali -- dia enumerasi SEMUA elemen yang match satu selector CSS
(`a.persistent-link.blog-index-card-link.w-inline-block`) lewat
`page.locator(...).count()`/`.nth(i)`. Diterjemahin ke XPath equivalen
(cek tiap token class-nya lewat `contains()`, bukan `@class="..."` -- posisi
class di atribut bisa beda urutan) + `indexed=False` (satu XPath -> banyak
node, di-zip title/link -- lihat `XPathScraper._extract_zipped`).

CATATAN: script lama punya `print(message_list); exit()` PERSIS SEBELUM loop
`push_job()`-nya -- jadi loop itu gak pernah kesampaian, scraper ini
SELAMA INI gak pernah beneran ngirim apa-apa (dead code, bukan disengaja).
Logic ekstraksinya sendiri tetap valid, jadi diselamatkan; bug `exit()`-nya
SENGAJA gak ikut di-port (sama kayak bug lain yang tercatat di
KNOWN_BROKEN.md).
"""

from __future__ import annotations

from cti_scraper.base import ScraperMeta
from cti_scraper.families.xpath import XPathScraper
from cti_scraper.schedule import spread

_CARD = (
    '//a[contains(concat(" ", normalize-space(@class), " "), " persistent-link ")'
    ' and contains(concat(" ", normalize-space(@class), " "), " blog-index-card-link ")'
    ' and contains(concat(" ", normalize-space(@class), " "), " w-inline-block ")]'
)


class Huntress(XPathScraper):
    meta = ScraperMeta(
        id="huntress",
        source="Huntress",
        schedule=spread("30 * * * *", "huntress"),
        runtime="browser",
        rate_limit="6/minute",
        tags=("migrated",),
        legacy_label="NEW ARTICLE FROM HUNTRESS",
        legacy_script="huntressThreat",
    )
    url = "https://www.huntress.com/blog?categories=Threat+Analysis%2CHuntress+News%2CCybersecurity+Trends"
    title_xpath = _CARD  # text_content() atas elemen <a> -- setara .inner_text() lama
    link_xpath = f"{_CARD}/@href"
    base_url = "https://www.huntress.com"
    indexed = False
