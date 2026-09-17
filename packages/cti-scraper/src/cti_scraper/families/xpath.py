"""XPathScraper -- declarative HTML+XPath. SATU class buat dua cara ambil
HTML; bedanya cuma `meta.runtime`, ekstraksinya identik:

  runtime="light"   -> httpx + lxml (gantiin ~11 scraper requests+lxml lama)
  runtime="browser" -> Playwright     (gantiin ~45 scraper Playwright lama)

Ini juga tempat kelas bug `securityaffairsThreat.py` (pakai `lxml.html`
tapi lupa import-nya) gak mungkin lagi kejadian -- import-nya ada di sini,
di framework, bukan di 56 file scraper yang masing-masing bisa lupa.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, ClassVar
from urllib.parse import urljoin

import lxml.html

from cti_scraper.base import BaseScraper, ScrapeContext
from cti_scraper.errors import ParseError
from cti_scraper.items import ArticleItem

if TYPE_CHECKING:
    from lxml.html import HtmlElement


class XPathScraper(BaseScraper):
    __abstract__ = True

    url: ClassVar[str]
    title_xpath: ClassVar[str]
    """Boleh punya placeholder `{i}` kalau `indexed=True` (pola umum
    scraper lama: card ke-N di halaman, mis. `range(1, 5)`)."""
    link_xpath: ClassVar[str]
    date_xpath: ClassVar[str | None] = None
    base_url: ClassVar[str] = ""
    indexed: ClassVar[bool] = True
    """True: `title_xpath`/`link_xpath` di-substitusi `{i}` dan diiterasi
    1..max_items (satu XPath per kartu). False: satu XPath -> list node,
    di-zip pasangan title/link (satu XPath buat semua kartu sekaligus)."""
    wait_for: ClassVar[str | None] = None
    """Browser doang -- CSS selector yang ditunggu sebelum `page.content()`."""

    def fetch(self, ctx: ScrapeContext) -> Iterator[ArticleItem]:
        html = self._get_html(ctx)
        tree = lxml.html.fromstring(html)

        found = 0
        for item in self._extract(tree, ctx):
            yield item
            found += 1
            if found >= self.meta.max_items:
                return

        if found == 0:
            raise ParseError(f"{self.url}: title_xpath={self.title_xpath!r} gak match apa pun")

    def _get_html(self, ctx: ScrapeContext) -> str:
        if self.meta.runtime == "browser":
            with ctx.page() as page:
                page.goto(self.url, wait_until="domcontentloaded")
                if self.wait_for:
                    page.wait_for_selector(self.wait_for, timeout=int(self.meta.timeout_s * 1000))
                return page.content()
        return ctx.http.get(self.url).text

    def _extract(self, tree: HtmlElement, ctx: ScrapeContext) -> Iterator[ArticleItem]:
        if self.indexed:
            yield from self._extract_indexed(tree, ctx)
        else:
            yield from self._extract_zipped(tree, ctx)

    def _extract_indexed(self, tree: HtmlElement, ctx: ScrapeContext) -> Iterator[ArticleItem]:
        for i in range(1, self.meta.max_items + 1):
            title_nodes = tree.xpath(self.title_xpath.format(i=i))
            link_nodes = tree.xpath(self.link_xpath.format(i=i))
            if not title_nodes or not link_nodes:
                continue
            item = self._build_item(title_nodes[0], link_nodes[0], ctx)
            if item is not None:
                yield item

    def _extract_zipped(self, tree: HtmlElement, ctx: ScrapeContext) -> Iterator[ArticleItem]:
        title_nodes = tree.xpath(self.title_xpath)
        link_nodes = tree.xpath(self.link_xpath)
        for title_node, link_node in zip(title_nodes, link_nodes, strict=False):
            item = self._build_item(title_node, link_node, ctx)
            if item is not None:
                yield item

    def _build_item(
        self, title_node: object, link_node: object, ctx: ScrapeContext
    ) -> ArticleItem | None:
        title = _text_of(title_node)
        url = _href_of(link_node, self.base_url)
        if not title or not url:
            return None
        return ArticleItem(title=title, url=url, posted_on=ctx.now.date())


def _text_of(node: object) -> str:
    if isinstance(node, str):
        return node.strip()
    text = node.text_content() if hasattr(node, "text_content") else ""
    return text.strip()


def _href_of(node: object, base_url: str) -> str:
    if isinstance(node, str):  # noqa: SIM108 -- ternary nested-nya lebih susah dibaca
        href = node
    else:
        href = node.get("href", "") if hasattr(node, "get") else ""
    if base_url and href and not href.startswith("http"):
        href = urljoin(base_url, href)
    return href
