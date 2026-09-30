"""Perbaikan selector ketemu census staging 2026-09-30 (WARP dimatikan, 24/94 masih gagal --
lihat `docs/PROGRESS.md`). Dua yang paling gampang diverifikasi live lalu diperbaiki di sini:

  - `doyensec`: bug MIGRASI (bukan situs berubah) -- feednya Atom sejak awal, tapi codemod Fase 4
    nge-generate scraper ini pakai default `RSSScraper` yang RSS-shaped.
  - `trustwave`: URL feed pindah (rebrand jadi LevelBlue). URL lama 301 ke feed yang SENGAJA
    dikosongkan sumbernya (`[DO NOT USE]`, nol `<item>`) -- bukan `item_path` yang salah.
"""

from __future__ import annotations

import httpx
import pytest
from cti_scraper.errors import ParseError
from cti_scrapers.feeds.doyensec import Doyensec
from cti_scrapers.feeds.trustwave import Trustwave

from tests.unit.scraper_helpers import make_ctx

# Potongan nyata dari `https://blog.doyensec.com/atom.xml` (ditarik 2026-09-30), dipangkas.
ATOM_FEED = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
 <title>Doyensec's Blog</title>
 <link href="https://blog.doyensec.com/atom.xml" rel="self"/>
 <link href="https://blog.doyensec.com/"/>
 <updated>2026-09-24T17:19:17+02:00</updated>
 <id>https://blog.doyensec.com</id>
 <entry>
   <title>One Tap Too Far: Using Shortcuts to Bypass Chrome for iOS Call Prompts</title>
   <link href="https://blog.doyensec.com/2026/09/24/chrome-ios-policy-bypass.html"/>
   <updated>2026-09-24T00:00:00+02:00</updated>
   <id>https://blog.doyensec.com/2026/09/24/chrome-ios-policy-bypass</id>
 </entry>
 <entry>
   <title>Second Post</title>
   <link href="https://blog.doyensec.com/2026/09/20/second-post.html"/>
   <updated>2026-09-20T00:00:00+02:00</updated>
 </entry>
</feed>
"""

# Potongan nyata dari `https://www.levelblue.com/blogs/spiderlabs-blog/rss.xml` (2026-09-30).
LEVELBLUE_FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:content="http://purl.org/rss/1.0/modules/content/" version="2.0">
  <channel>
    <title>LevelBlue SpiderLabs Blog</title>
    <link>https://www.levelblue.com/blogs/spiderlabs-blog</link>
    <item>
      <title>Citrix NetScaler Zero-Day Exploited Globally</title>
      <link>https://www.levelblue.com/blogs/spiderlabs-blog/citrix-netscaler-zero-day-exploited-globally</link>
      <pubDate>Tue, 29 Sep 2026 12:29:55 GMT</pubDate>
    </item>
  </channel>
</rss>
"""

# Bentuk NYATA dari redirect target URL lama (`www.trustwave.com/.../rss.xml` -> 301 ->
# `www.levelblue.com/en-us/.../rss.xml`) -- channel valid TAPI nol <item>, sengaja dikosongkan.
DO_NOT_USE_STUB = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:dc="http://purl.org/dc/elements/1.1/" version="2.0">
  <channel>
    <title>[DO NOT USE] SpiderLabs Blog</title>
    <link>https://www.levelblue.com/en-us/resources/blogs/spiderlabs-blog</link>
  </channel>
</rss>
"""


def test_doyensec_parses_atom_entries_not_rss_items() -> None:
    ctx = make_ctx(Doyensec, lambda r: httpx.Response(200, content=ATOM_FEED))

    items = list(Doyensec().fetch(ctx))

    assert [i.title for i in items] == [
        "One Tap Too Far: Using Shortcuts to Bypass Chrome for iOS Call Prompts",
        "Second Post",
    ]
    assert items[0].url == "https://blog.doyensec.com/2026/09/24/chrome-ios-policy-bypass.html"


def test_doyensec_rss_default_would_find_nothing_in_this_feed() -> None:
    """Pagar regresi: buktikan bug LAMA (default RSS `RSSScraper`, tanpa override Atom) beneran
    gagal di fixture ATOM ini -- kalau override di `Doyensec` kehapus/salah, test PERTAMA
    (`test_doyensec_parses_atom_entries_not_rss_items`) yang harus gagal, bukan test ini."""
    from cti_scraper.base import ScraperMeta
    from cti_scraper.families.rss import RSSScraper
    from cti_scraper.schedule import spread

    class _UnpatchedRssDefault(RSSScraper):
        meta = ScraperMeta(id="unpatched", source="x", schedule=spread("0 * * * *", "unpatched"))
        feeds = Doyensec.feeds

    ctx = make_ctx(_UnpatchedRssDefault, lambda r: httpx.Response(200, content=ATOM_FEED))

    with pytest.raises(ParseError, match=r"item_path='\.//item'"):
        list(_UnpatchedRssDefault().fetch(ctx))


def test_trustwave_uses_the_levelblue_url_and_parses_it() -> None:
    ctx = make_ctx(Trustwave, lambda r: httpx.Response(200, content=LEVELBLUE_FEED))

    items = list(Trustwave().fetch(ctx))

    assert [i.title for i in items] == ["Citrix NetScaler Zero-Day Exploited Globally"]
    assert items[0].url == (
        "https://www.levelblue.com/blogs/spiderlabs-blog/citrix-netscaler-zero-day-exploited-globally"
    )


def test_trustwave_feeds_no_longer_points_at_the_dead_old_url() -> None:
    assert Trustwave.feeds == ("https://www.levelblue.com/blogs/spiderlabs-blog/rss.xml",)
    assert "trustwave.com" not in Trustwave.feeds[0]


def test_the_old_redirect_target_really_is_an_intentionally_empty_stub() -> None:
    """Dokumentasi keputusan: BUKAN `item_path` yang salah. Kalau scraper masih pakai URL lama,
    ini yang bakal ke-parse -- channel-nya sendiri kosong, jadi hasilnya `ParseError` "gak ada
    node", SAMA PERSIS klasifikasi census (bukan status baru/berbeda kalau url-nya gak diganti)."""
    ctx = make_ctx(Trustwave, lambda r: httpx.Response(200, content=DO_NOT_USE_STUB))

    with pytest.raises(ParseError, match=r"gak ada node di item_path"):
        list(Trustwave().fetch(ctx))
