"""RSSScraper -- declarative RSS/Atom. Nutupin ~142 dari 241 scraper lama
(~59%, family paling besar). Subclass, isi `feeds`, selesai.

Bandingkan sama `gbHackerThreat.py` asli (43 baris): UA header, cabang
status-code, rantai `.replace()` ad-hoc buat entity malformed, loop
`is_new_and_mark`/`push_job` -- semua itu boilerplate yang di sini jadi
default yang jalan. Hasil migrasinya di
`scrapers/src/cti_scrapers/feeds/gbhackers.py` cuma ~10 baris.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from email.utils import parsedate_to_datetime
from typing import ClassVar
from urllib.parse import urljoin
from xml.etree.ElementTree import Element
from xml.etree.ElementTree import ParseError as XmlParseError

import defusedxml.ElementTree as ET

from cti_scraper.base import BaseScraper, ScrapeContext
from cti_scraper.errors import ParseError
from cti_scraper.items import ArticleItem


class RSSScraper(BaseScraper):
    __abstract__ = True

    feeds: ClassVar[tuple[str, ...]]
    item_path: ClassVar[str] = ".//item"
    """XPath-lite ElementTree, mis. ".//item" (RSS) atau
    ".//{http://www.w3.org/2005/Atom}entry" (Atom -- namespace wajib eksplisit)."""
    title_path: ClassVar[str] = "title"
    link_path: ClassVar[str] = "link"
    date_path: ClassVar[str | None] = "pubDate"
    link_attr: ClassVar[str | None] = None
    """None: ambil `.text` node link (RSS). Diisi "href": ambil attribute
    itu (Atom, `<link href="..."/>`)."""
    base_url: ClassVar[str] = ""
    """Prefix buat link relatif. Kosongin kalau feed-nya selalu absolut
    (mayoritas kasus)."""
    xml_fixups: ClassVar[tuple[tuple[str, str], ...]] = ()
    """Pasangan (cari, ganti) di-apply ke teks MENTAH sebelum parse XML.
    Lifted dari rantai `.replace()` ad-hoc yang tiap scraper lama punya
    sendiri buat entity yang malformed -- kebanyakan scraper hasil migrasi
    gak butuh ini sama sekali karena defusedxml + recover di bawah udah
    nanganin kasus umum."""

    def fetch(self, ctx: ScrapeContext) -> Iterator[ArticleItem]:
        found_total = 0
        for feed_url in self.feeds:
            for item in self._parse_feed(ctx, feed_url):
                if found_total >= self.meta.max_items:
                    return
                found_total += 1
                yield item

    def _parse_feed(self, ctx: ScrapeContext, feed_url: str) -> Iterator[ArticleItem]:
        resp = ctx.http.get(feed_url)
        text = resp.text
        for old, new in self.xml_fixups:
            text = text.replace(old, new)

        try:
            root = ET.fromstring(text.encode("utf-8"))
        except XmlParseError as e:
            raise ParseError(f"{feed_url}: XML gak valid -- {e}") from e

        nodes = root.findall(self.item_path)
        if not nodes:
            raise ParseError(f"{feed_url}: gak ada node di item_path={self.item_path!r}")

        for node in nodes:
            item = self._parse_item(node, ctx)
            if item is not None:
                yield item

    def _parse_item(self, node: Element, ctx: ScrapeContext) -> ArticleItem | None:
        title_el = node.find(self.title_path)
        link_el = node.find(self.link_path)
        if title_el is None or link_el is None:
            return None

        title = (title_el.text or "").strip()
        url = link_el.get(self.link_attr, "") if self.link_attr else (link_el.text or "").strip()
        if not title or not url:
            return None
        if self.base_url and not url.startswith("http"):
            url = urljoin(self.base_url, url)

        posted_on = ctx.now.date()
        if self.date_path is not None:
            date_el = node.find(self.date_path)
            if date_el is not None and date_el.text:
                parsed = _parse_rfc822_date(date_el.text)
                if parsed is not None:
                    posted_on = parsed

        return ArticleItem(title=title, url=url, posted_on=posted_on)


def _parse_rfc822_date(text: str) -> date | None:
    try:
        return parsedate_to_datetime(text).date()
    except (TypeError, ValueError):
        return None
