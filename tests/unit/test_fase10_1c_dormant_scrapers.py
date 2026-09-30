"""Port item 10.1c (2026-09-30): 6 scraper Selenium yang nonaktif/disabled di
Rundeck lama. Test ini nutupin `forcepoint` (XPath) -- `toxinlabs` (RSS/Atom)
diverifikasi di `test_rss_illegal_xml_chars.py`. `trellix` DROPPED (keputusan
user 2026-09-30): kode+selector-nya benar, tapi fetch produksi diblokir CDN
(`net::ERR_HTTP2_PROTOCOL_ERROR`, konsisten di 2 network) -- lihat
`docs/PROGRESS.md` 10.1c buat detail lengkap kenapa di-drop.

Fixture di bawah adalah potongan NYATA dari DOM live (diverifikasi lewat
browser interaktif 2026-09-30, dipangkas), bukan HTML karangan -- termasuk
struktur kartu forcepoint yang gak seragam (hero pakai `<h2>` nested di
beberapa `<div>`, kartu grid pakai `<h4>` langsung anak `<a>`) yang jadi
alasan `Forcepoint` pakai `indexed=False` + XPath union, bukan `{i}` tetap.
"""

from __future__ import annotations

import lxml.html
from cti_scrapers.feeds.forcepoint import Forcepoint

from tests.unit.scraper_helpers import make_ctx

HERO_TITLE = "AI Red Teaming Cannot Show What Data a Jailbreak Exposed"
GRID_TITLE_1 = "No Hidden Text Required to Fool an AI Email Summarizer"
GRID_TITLE_2 = "AI Governance vs. AI Compliance: Where They Diverge"

FORCEPOINT_HTML = f"""
<html><body><main>
  <div>
    <div>
      <a href="/blog/insights/ai-red-teaming-data-security">
        <div><div><div><h2>{HERO_TITLE}</h2></div></div></div>
      </a>
    </div>
    <div>
      <a href="/blog/x-labs/hiding-vs-instruction-prompt-injection">
        <h4>{GRID_TITLE_1}</h4>
      </a>
    </div>
    <div><a href="/newsletter">Get insight, analysis &amp; news</a></div>
    <div>
      <a href="/blog/insights/ai-governance-vs-ai-compliance">
        <h4>{GRID_TITLE_2}</h4>
      </a>
    </div>
  </div>
</main></body></html>
"""


def test_forcepoint_extracts_hero_and_grid_cards_in_order() -> None:
    tree = lxml.html.fromstring(FORCEPOINT_HTML)
    ctx = make_ctx(Forcepoint, lambda r: None)

    items = list(Forcepoint()._extract(tree, ctx))

    assert [i.title for i in items] == [HERO_TITLE, GRID_TITLE_1, GRID_TITLE_2]
    assert items[0].url == "https://www.forcepoint.com/blog/insights/ai-red-teaming-data-security"


def test_forcepoint_indexed_default_would_duplicate_the_hero_card() -> None:
    """Pagar regresi: `title_xpath`/`link_xpath` di `Forcepoint` itu XPath union TANPA `{i}`
    (lihat docstring), jadi `indexed=True` default bakal manggil `.format(i=i)` yang gak ngubah
    apa-apa dan `[0]` ke node PERTAMA yang sama tiap iterasi -- bukan "gak nemu apa-apa", tapi
    nge-duplikasi hero card `max_items` kali. Buktikan `indexed=False` itu perlu, bukan opsional."""
    tree = lxml.html.fromstring(FORCEPOINT_HTML)
    ctx = make_ctx(Forcepoint, lambda r: None)

    scraper = Forcepoint()
    items_indexed_mode = list(scraper._extract_indexed(tree, ctx))

    assert [i.title for i in items_indexed_mode] == [HERO_TITLE] * 5
