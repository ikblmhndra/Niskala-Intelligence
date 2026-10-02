"""Fase 10.D (2026-10-01): 8 scraper XPath yang selector-nya lapuk diganti ke `RSSScraper` karena
situsnya punya feed resmi (ketemu lewat probe path umum, bukan dari `<link rel="alternate">`).

Judul/URL di fixture diambil dari feed ASLI hari itu (dipangkas ke 2 item). Test memastikan tiga hal
yang bisa diam-diam rusak: (1) URL feed yang dipukul, (2) hasil ekstraksi item, (3) `max_items`
untuk feed yang memuat seluruh arsip blog (tanpa batas, run pertama ngantri puluhan artikel lama).
"""

from __future__ import annotations

import httpx
import pytest
from cti_scraper.families.rss import RSSScraper
from cti_scrapers.feeds.aquasec import Aquasec
from cti_scrapers.feeds.cloudflare import Cloudflare
from cti_scrapers.feeds.cymru import Cymru
from cti_scrapers.feeds.groupib import Groupib
from cti_scrapers.feeds.huntress import Huntress
from cti_scrapers.feeds.intel471 import Intel471
from cti_scrapers.feeds.landth import Landth
from cti_scrapers.feeds.sysdig import Sysdig

from tests.unit.scraper_helpers import make_ctx


def _rss(items: list[tuple[str, str]]) -> bytes:
    body = "".join(
        f"<item><title>{t}</title><link>{u}</link>"
        "<pubDate>Wed, 30 Sep 2026 10:00:00 GMT</pubDate></item>"
        for t, u in items
    )
    head = '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>x</title>'
    return f"{head}{body}</channel></rss>".encode()


# (kelas, URL feed yang diharapkan, 2 item nyata dari feed-nya)
CASES = [
    (
        Aquasec,
        "https://www.aquasec.com/feed/",
        [
            (
                "Supply Chain Security Has the Operating Model Backwards",
                "https://www.aquasec.com/blog/supply-chain-security-has-the-operating-model-backwards/",
            ),
            (
                "Why Is Detection and Response Too Slow for Machine Speed?",
                "https://www.aquasec.com/blog/why-is-detection-and-response-too-slow-for-machine-speed/",
            ),
        ],
    ),
    (
        Groupib,
        "https://www.group-ib.com/feed/blogfeed/",
        [
            (
                "RemControl: AI Built the Overlays. Victims Lose their PINs",
                "https://www.group-ib.com/blog/remcontrol-android-banking-trojan/",
            ),
            (
                "HEAVYGRAM: A Telegram-based Surveillance Backdoor",
                "https://www.group-ib.com/blog/heavygram-handala-hack-telegram-c2/",
            ),
        ],
    ),
    (
        Huntress,
        "https://www.huntress.com/blog/rss.xml",
        [
            (
                "Determined Attacker Uploads Malicious Webshells to Parks",
                "https://www.huntress.com/blog/parks-recreation-platform-webshell-attack",
            ),
            (
                "Meet Athena: Huntress' Agentic SOC Analyst",
                "https://www.huntress.com/blog/athena-huntress-agentic-soc-analyst",
            ),
        ],
    ),
    (
        Landth,
        "https://depi.security/rss.xml",
        [
            (
                "npx Used Confusion and It's Super Effective",
                "https://depi.security/blog/20260521-npx-used-confusion-and-its-super-effective",
            ),
            (
                "node-ipc Compromised: A Dormant Maintainer",
                "https://depi.security/blog/20260514-node-ipc-compromised",
            ),
        ],
    ),
    (
        Cymru,
        "https://www.team-cymru.com/post/rss.xml",
        [
            (
                "From C2 Detection to Possible Victim Identification",
                "https://www.team-cymru.com/post/c2-detection-to-victim-identification",
            ),
            (
                "Modernizing Incident Response: 4 Steps to Bulletproof Your Workflow",
                "https://www.team-cymru.com/post/modernizing-incident-response-4-steps",
            ),
        ],
    ),
    (
        Cloudflare,
        "https://blog.cloudflare.com/tag/security/rss/",
        [
            (
                "Building a certificate authority for the whole Internet",
                "https://blog.cloudflare.com/cloudflare-certificate-authority/",
            ),
            (
                "Using AI to chart a course for our post-quantum migration",
                "https://blog.cloudflare.com/ai-driven-cryptography-discovery/",
            ),
        ],
    ),
    (
        Intel471,
        "https://www.intel471.com/blog/feed",
        [
            (
                "Insiders for Hire: How the Underground Market for Employee Access Works",
                "https://www.intel471.com/blog/insiders-for-hire",
            ),
            (
                "Another Intel 471 Post",
                "https://www.intel471.com/blog/another-post",
            ),
        ],
    ),
]

# Feed yang memuat SELURUH arsip blog -- dibatasi 10 (feed lain pakai default framework).
CAPPED_AT_10 = {Groupib, Huntress, Sysdig, Intel471}


@pytest.mark.parametrize(("cls", "feed_url", "items"), CASES, ids=[c[0].__name__ for c in CASES])
def test_pukul_url_feed_yang_benar_dan_ekstrak_item(
    cls: type[RSSScraper], feed_url: str, items: list[tuple[str, str]]
) -> None:
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return httpx.Response(200, content=_rss(items))

    got = list(cls().fetch(make_ctx(cls, handler)))

    assert requested == [feed_url]
    assert [(i.title, i.url) for i in got] == items


@pytest.mark.parametrize("cls", [c[0] for c in CASES] + [Sysdig], ids=lambda c: c.__name__)
def test_semua_hasil_konversi_pakai_runtime_light(cls: type[RSSScraper]) -> None:
    """Gak butuh Chromium lagi -- inti konversinya (lebih murah & awet dari XPath absolut)."""
    assert cls.meta.runtime == "light"


@pytest.mark.parametrize(
    "cls", sorted(CAPPED_AT_10, key=lambda c: c.__name__), ids=lambda c: c.__name__
)
def test_feed_arsip_penuh_dibatasi_10_item(cls: type[RSSScraper]) -> None:
    many = [(f"Post {n}", f"https://example.com/p/{n}") for n in range(25)]

    got = list(cls().fetch(make_ctx(cls, lambda r: httpx.Response(200, content=_rss(many)))))

    assert len(got) == 10


def test_sysdig_url_host_staging_webflow_diganti_host_publik() -> None:
    """Feed Sysdig mengisi `<link>` dengan host staging Webflow (`webflow.sysdig.com`) -- kalau gak
    diganti, URL yang tersimpan/di-alert salah host dan dedup gak cocok sama URL canonical."""
    feed = _rss(
        [
            (
                "AI adoption is a security survival metric",
                "https://webflow.sysdig.com/blog/ai-adoption-is-a-security-survival-metric",
            )
        ]
    )

    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return httpx.Response(200, content=feed)

    got = list(Sysdig().fetch(make_ctx(Sysdig, handler)))

    assert requested == ["https://www.sysdig.com/blog/rss.xml"]
    assert [i.url for i in got] == [
        "https://www.sysdig.com/blog/ai-adoption-is-a-security-survival-metric"
    ]
