"""Fase 10.D (2026-10-01): `sentinel` dan `crowdstrike` `empty` 20/20 run per 24 jam.

Keduanya meng-port filter kategori script lama, dan situsnya sudah mengganti taksonomi.
Feed SentinelOne Labs sekarang memakai "Adversary"/"AI Research"/"LABScon" (bukan "From the
Front Lines"); blog CrowdStrike mengganti "Counter Adversary Operations" jadi "Threat Hunting
& Intel". Hasilnya SEMUA item dibuang filter. Kesimpulan lama "filter sah" (KNOWN_BROKEN.md,
Fase 0.5) basi begitu situsnya berubah. Kategori di fixture diambil dari feed ASLI hari itu.
"""

from __future__ import annotations

import httpx
import pytest
from cti_scraper.families.rss import RSSScraper
from cti_scrapers.feeds.crowdstrike import Crowdstrike
from cti_scrapers.feeds.sentinel import Sentinel

from tests.unit.scraper_helpers import make_ctx


def _feed(items: list[tuple[str, list[str]]]) -> bytes:
    body = "".join(
        f"<item><title>{t}</title><link>https://example.com/{n}</link>"
        + "".join(f"<category><![CDATA[{c}]]></category>" for c in cats)
        + "</item>"
        for n, (t, cats) in enumerate(items)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>x</title>'
        f"{body}</channel></rss>"
    ).encode()


def _titles(cls: type[RSSScraper], items: list[tuple[str, list[str]]]) -> list[str]:
    ctx = make_ctx(cls, lambda r: httpx.Response(200, content=_feed(items)))
    return [i.title for i in cls().fetch(ctx)]


@pytest.mark.parametrize(
    "category", ["Adversary", "AI Research", "LABScon", "From the Front Lines"]
)
def test_sentinel_menerima_kategori_baru_dan_lama(category: str) -> None:
    assert _titles(Sentinel, [("Laporan riset", [category, "macos"])]) == ["Laporan riset"]


def test_sentinel_tetap_membuang_kategori_di_luar_daftar_dan_meloloskan_tanpa_kategori() -> None:
    items = [
        ("Produk", ["Product News"]),
        ("Riset", ["Adversary"]),
        ("Tanpa kategori", []),
    ]

    assert _titles(Sentinel, items) == ["Riset", "Tanpa kategori"]


@pytest.mark.parametrize("category", ["Threat Hunting & Intel", "Counter Adversary Operations"])
def test_crowdstrike_menerima_nama_kategori_baru_dan_lama(category: str) -> None:
    # `&` di feed asli bentuknya `&amp;` -- lewat jalur `xml_fixups` + `html_unescape` scraper ini.
    raw = category.replace("&", "&amp;")
    ctx = make_ctx(
        Crowdstrike,
        lambda r: httpx.Response(
            200,
            content=(
                '<?xml version="1.0"?><rss version="2.0"><channel><title>x</title>'
                f"<item><title>Posting</title><link>https://example.com/1</link>"
                f"<category>{raw}</category></item></channel></rss>"
            ).encode(),
        ),
    )

    assert [i.title for i in Crowdstrike().fetch(ctx)] == ["Posting"]


def test_crowdstrike_tetap_membuang_kategori_lain() -> None:
    items = [("Produk", ["Securing AI"]), ("Riset", ["Threat Hunting & Intel"])]
    ctx = make_ctx(
        Crowdstrike,
        lambda r: httpx.Response(
            200,
            content=(
                '<?xml version="1.0"?><rss version="2.0"><channel><title>x</title>'
                + "".join(
                    f"<item><title>{t}</title><link>https://example.com/{n}</link>"
                    f"<category>{c[0].replace('&', '&amp;')}</category></item>"
                    for n, (t, c) in enumerate(items)
                )
                + "</channel></rss>"
            ).encode(),
        ),
    )

    assert [i.title for i in Crowdstrike().fetch(ctx)] == ["Riset"]
