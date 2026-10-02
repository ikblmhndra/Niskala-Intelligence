"""Fase 10.D (2026-10-01): 8 scraper yang XPath absolutnya lapuk diganti `link_card_xpaths`
(pola href artikel, bukan posisi div ke-N), plus 5 scraper yang di-waiver (`enabled=False`).

Bentuk link di fixture diambil dari DOM ASLI hasil render (probe 2026-10-01): href relatif
`./blog/..` (hunt.io), absolut (dragos/sans/abnormal), label kategori + tanggal di dalam anchor
(proofpoint/sans), anchor tanpa heading (hero abnormal, splunk, cis, dragos). Tiap fixture juga
menyelipkan JEBAKAN: link menu di `header` dan link footer yang polanya sama tapi bukan artikel.
"""

from __future__ import annotations

from typing import Any

import lxml.html
import pytest
from cti_scraper.families.xpath import XPathScraper
from cti_scrapers.feeds._links import link_card_xpaths
from cti_scrapers.feeds.abnormalsecurity import Abnormalsecurity
from cti_scrapers.feeds.blackberry import Blackberry
from cti_scrapers.feeds.cis import Cis
from cti_scrapers.feeds.cisa import Cisa
from cti_scrapers.feeds.dragos import Dragos
from cti_scrapers.feeds.google import Google
from cti_scrapers.feeds.huntio import Huntio
from cti_scrapers.feeds.koisec import Koisec
from cti_scrapers.feeds.nquiring_minds import NquiringMinds
from cti_scrapers.feeds.prodraft import Prodraft
from cti_scrapers.feeds.proofpoint import Proofpoint
from cti_scrapers.feeds.sans import Sans
from cti_scrapers.feeds.splunk import Splunk

from tests.unit.scraper_helpers import make_ctx


def _page(nav_href: str, footer_href: str, cards: str) -> str:
    return (
        f'<html><body><header><a href="{nav_href}">Blog Home Page And Navigation</a></header>'
        f"<main>{cards}</main>"
        f'<footer><a href="{footer_href}">Footer link with a long enough text to pass</a></footer>'
        "</body></html>"
    )


def _extract(cls: type[XPathScraper], html: str) -> list[tuple[str, str]]:
    ctx = make_ctx(cls, lambda r: None)
    return [(i.title, i.url) for i in cls()._extract(lxml.html.fromstring(html), ctx)]


def _plain(href: str, title: str) -> str:
    return f'<div><a href="{href}">{title}</a></div>'


def _headed(href: str, label: str, title: str) -> str:
    inner = f"<span>{label}</span><h3>{title}</h3><p>ringkasan panjang</p>"
    return f'<div><a href="{href}">{inner}</a></div>'


# (kelas, [(HTML kartu, judul diharapkan, URL absolut diharapkan)], nav_href, footer_href)
CASES = [
    (
        Abnormalsecurity,
        [
            (
                _plain(
                    "https://abnormal.ai/blog/ai-security-suite-announcement",
                    "Expanding our AI Security Suite, Powered by Behavioral AI",
                ),
                "Expanding our AI Security Suite, Powered by Behavioral AI",
                "https://abnormal.ai/blog/ai-security-suite-announcement",
            ),
            (
                _headed(
                    "/blog/behavioral-ai-security-platform?from=blog",
                    "PRODUCT",
                    "The Behavioral Security Era is Here: Securing Identity",
                ),
                "The Behavioral Security Era is Here: Securing Identity",
                "https://abnormal.ai/blog/behavioral-ai-security-platform?from=blog",
            ),
        ],
        "/blog/",
        "/blog/footer-article-with-matching-prefix",
    ),
    (
        Huntio,
        [
            (
                _plain(
                    "./blog/silkparasite-spicerat-central-asia-infrastructure",
                    "SilkParasite Infrastructure: SpiceRAT Servers Tied to Energy Targets",
                ),
                "SilkParasite Infrastructure: SpiceRAT Servers Tied to Energy Targets",
                "https://hunt.io/blog/silkparasite-spicerat-central-asia-infrastructure",
            ),
            (
                _plain(
                    "./blog/operation-cameraswarm-dahua-cameras-compromised",
                    "Operation CameraSwarm: Over 14,000 Dahua cameras compromised",
                ),
                "Operation CameraSwarm: Over 14,000 Dahua cameras compromised",
                "https://hunt.io/blog/operation-cameraswarm-dahua-cameras-compromised",
            ),
        ],
        "./blog/",
        "./blog/footer-article-with-matching-prefix",
    ),
    (
        Prodraft,
        [
            (
                _headed(
                    "/blog/why-does-systembc-dominate-the-ransomware-scene",
                    "RANSOMWARE",
                    "Why Does SystemBC Dominate the Ransomware Scene?",
                ),
                "Why Does SystemBC Dominate the Ransomware Scene?",
                "https://www.prodaft.com/blog/why-does-systembc-dominate-the-ransomware-scene",
            ),
        ],
        "/blog/",
        "/blog/footer-article-with-matching-prefix",
    ),
    (
        Sans,
        [
            (
                _headed(
                    "https://www.sans.org/white-papers/invisible-default-polyglot-smuggler",
                    "WHITEPAPER OFFENSIVE OPERATIONS 1 Oct",
                    "Invisible by Default: The Polyglot Smuggler",
                ),
                "Invisible by Default: The Polyglot Smuggler",
                "https://www.sans.org/white-papers/invisible-default-polyglot-smuggler",
            ),
        ],
        "/white-papers/",
        "/white-papers/footer-article-with-matching-prefix",
    ),
    (
        Splunk,
        [
            (
                _plain(
                    "/en_us/blog/security/building-agentic-socs-at-the-toughest-live-events.html",
                    "What We Learned Building Agentic SOCs at the Toughest Live Events",
                ),
                "What We Learned Building Agentic SOCs at the Toughest Live Events",
                "https://www.splunk.com/en_us/blog/security/building-agentic-socs-at-the-toughest-live-events.html",
            ),
        ],
        "/en_us/blog/security/",
        "/en_us/blog/security/footer-article-with-matching-prefix",
    ),
    (
        Proofpoint,
        [
            (
                _headed(
                    "/us/blog/threat-insight/Spraying-in-the-Andes-TeamFiltration-Returns",
                    "Threat Insight September 22, 2026 Pavel Asinovsky",
                    "Spraying in the Andes: TeamFiltration Returns",
                ),
                "Spraying in the Andes: TeamFiltration Returns",
                "https://www.proofpoint.com/us/blog/threat-insight/Spraying-in-the-Andes-TeamFiltration-Returns",
            ),
        ],
        "/us/blog/threat-insight/",
        "/us/blog/threat-insight/footer-article-with-matching-prefix",
    ),
    (
        Cis,
        [
            (
                _plain(
                    "/advisory/a-vulnerability-in-cisco-catalyst-sd-wan-manager-could-allow",
                    "2026-105: A Vulnerability in Cisco Catalyst SD-WAN Manager Could Allow",
                ),
                "2026-105: A Vulnerability in Cisco Catalyst SD-WAN Manager Could Allow",
                "https://www.cisecurity.org/advisory/a-vulnerability-in-cisco-catalyst-sd-wan-manager-could-allow",
            ),
        ],
        "/advisory/",
        "/advisory/footer-article-with-matching-prefix",
    ),
    (
        Dragos,
        [
            (
                _plain(
                    "https://www.dragos.com/blog/xot-software-supply-chain-security",
                    "Software and Supply Chain Security Can't Be an Afterthought in xOT",
                ),
                "Software and Supply Chain Security Can't Be an Afterthought in xOT",
                "https://www.dragos.com/blog/xot-software-supply-chain-security",
            ),
        ],
        "/blog/",
        "/blog/footer-article-with-matching-prefix",
    ),
]


@pytest.mark.parametrize(
    ("cls", "cards", "nav_href", "footer_href"),
    [(c[0], c[1], c[2], c[3]) for c in CASES],
    ids=[c[0].__name__ for c in CASES],
)
def test_ekstrak_artikel_tanpa_link_menu_dan_footer(
    cls: type[XPathScraper], cards: list[tuple[str, str, str]], nav_href: str, footer_href: str
) -> None:
    html = _page(nav_href, footer_href, "".join(c[0] for c in cards))

    got = _extract(cls, html)

    assert got == [(c[1], c[2]) for c in cards]


@pytest.mark.parametrize("cls", [c[0] for c in CASES], ids=lambda c: c.__name__)
def test_semua_pakai_mode_zipped_dan_menunggu_anchor_artikel(cls: type[XPathScraper]) -> None:
    assert cls.indexed is False
    assert cls.meta.runtime == "browser"
    assert cls.wait_for


def test_abnormal_wait_for_dibatasi_ke_main() -> None:
    """`wait_for_selector` nunggu elemen PERTAMA yang cocok jadi visible. Link `/blog/` di menu
    header itu tersembunyi, jadi tanpa `main` timeout 30 dtk (ketemu waktu verifikasi live)."""
    assert Abnormalsecurity.wait_for is not None
    assert Abnormalsecurity.wait_for.startswith("main ")


# ---- helper `link_card_xpaths` ----------------------------------------------------------------


def _xp(html: str, pred: str = "contains(@href, '/p/')") -> list[tuple[str, str]]:
    title_xp, link_xp = link_card_xpaths(pred)
    tree = lxml.html.fromstring(html)
    titles = [n if isinstance(n, str) else n.text_content().strip() for n in tree.xpath(title_xp)]
    links = [str(n) for n in tree.xpath(link_xp)]
    assert len(titles) == len(links), "title & link harus SEJAJAR (kontrak mode zipped)"
    return list(zip(titles, links, strict=True))


def test_helper_judul_dari_heading_pertama_bukan_label_kategori() -> None:
    html = (
        '<main><a href="/p/1"><span>PRODUCT</span><h3>Judul Satu Yang Cukup Panjang</h3>'
        "<h4>subjudul</h4><p>x</p></a></main>"
    )

    assert _xp(html) == [("Judul Satu Yang Cukup Panjang", "/p/1")]


@pytest.mark.parametrize("tag", ["h1", "h2", "h3", "h4", "h5"])
def test_helper_semua_level_heading_h1_sampai_h5_dikenali(tag: str) -> None:
    """Label di depan heading bikin judul = heading BERBEDA dari `text_content()` anchor -- tanpa
    ini mutasi yang membuang satu level heading dari daftar gak ketahuan."""
    heading = f"<{tag}>Judul untuk {tag} panjang</{tag}>"
    html = f'<main><a href="/p/1"><span>LABEL</span>{heading}</a></main>'

    assert _xp(html) == [(f"Judul untuk {tag} panjang", "/p/1")]


def test_helper_anchor_tanpa_heading_dipakai_teksnya_dan_urutan_dokumen_terjaga() -> None:
    html = (
        '<main><a href="/p/1">Artikel tanpa heading nomor satu</a>'
        '<a href="/p/2"><h2>Artikel dengan heading nomor dua</h2></a>'
        '<a href="/p/3">Artikel tanpa heading nomor tiga</a></main>'
    )

    assert _xp(html) == [
        ("Artikel tanpa heading nomor satu", "/p/1"),
        ("Artikel dengan heading nomor dua", "/p/2"),
        ("Artikel tanpa heading nomor tiga", "/p/3"),
    ]


def test_helper_buang_menu_footer_teks_pendek_dan_href_lain() -> None:
    html = (
        '<header><a href="/p/menu">Menu dengan teks yang cukup panjang</a></header>'
        '<nav><a href="/p/nav">Nav dengan teks yang cukup panjang</a></nav>'
        '<main><a href="/p/1">Artikel asli dengan teks cukup panjang</a>'
        '<a href="/p/2">Read more</a>'
        '<a href="/lain/3">Link dengan pola href yang berbeda sama sekali</a></main>'
        '<footer><a href="/p/foot">Footer dengan teks yang cukup panjang</a></footer>'
    )

    assert _xp(html) == [("Artikel asli dengan teks cukup panjang", "/p/1")]


def test_helper_ambang_min_text_bisa_diatur() -> None:
    html = '<main><a href="/p/1">Judul pendek</a></main>'
    title_xp, _ = link_card_xpaths("contains(@href, '/p/')", min_text=5)

    assert [n.text_content() for n in lxml.html.fromstring(html).xpath(title_xp)] == [
        "Judul pendek"
    ]
    assert _xp(html) == []  # default 20 karakter -> dibuang


def test_helper_anchor_dobel_tetap_sejajar() -> None:
    """Gambar + judul menunjuk URL yang sama -> item dobel; dedup di framework yang membuangnya."""
    html = (
        '<main><a href="/p/1">Artikel dengan gambar dan judul satu</a>'
        '<a href="/p/1">Artikel dengan gambar dan judul satu</a></main>'
    )

    assert len(_xp(html)) == 2


# ---- waiver --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cls", [Blackberry, Koisec, Google, Cisa, NquiringMinds], ids=lambda c: c.__name__
)
def test_scraper_waiver_tetap_nonaktif(cls: Any) -> None:
    """Sumbernya mati/diblokir (lihat docstring masing-masing + `docs/KNOWN_BROKEN.md`). Jangan
    sampai ke-enable lagi diam-diam -- tiap jam bakal gagal dan bikin health sweep berisik."""
    assert cls.meta.enabled is False
