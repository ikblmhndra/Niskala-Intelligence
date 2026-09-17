"""ApiScraper -- JSON API dengan field-map declarative. Nutupin ujung
paling simpel dari ~35 scraper bespoke lama (API yang langsung ngasih
daftar artikel). Yang beneran kompleks -- state lintas-bulan, kredensial
berbayar, bentuk dokumen sendiri (ransomware.live dkk) -- subclass
`BaseScraper` LANGSUNG, bukan class ini. Lihat
`scrapers/src/cti_scrapers/collectors/ransomware_live.py` buat contohnya.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, ClassVar

from cti_scraper.base import BaseScraper, ScrapeContext
from cti_scraper.errors import ParseError
from cti_scraper.items import ArticleItem, Item


class ApiScraper(BaseScraper):
    __abstract__ = True

    url: ClassVar[str]
    root_path: ClassVar[str] = ""
    """Kunci dict yang nunjuk ke list item. Kosong = respons ITU SENDIRI
    daftarnya (top-level JSON array)."""
    item_model: ClassVar[type[Item]] = ArticleItem
    field_map: ClassVar[dict[str, str]] = {}
    """{nama_field_item: kunci_json}, mis. {"title": "cve_id", "url": "cve_link"}.
    Baris yang kehilangan salah satu kunci ini di-skip diam-diam (dianggap
    baris parsial dari API, bukan error)."""
    params: ClassVar[dict[str, str]] = {}

    def fetch(self, ctx: ScrapeContext) -> Iterator[Item]:
        resp = ctx.http.get(self.url, params=self.params or None)
        try:
            payload = resp.json()
        except ValueError as e:
            raise ParseError(f"{self.url}: respons bukan JSON valid -- {e}") from e

        rows: Any = payload
        if self.root_path:
            rows = payload.get(self.root_path) if isinstance(payload, dict) else None

        if not isinstance(rows, list):
            raise ParseError(
                f"{self.url}: diharap list di root_path={self.root_path!r}, "
                f"dapet {type(rows).__name__}"
            )
        if not rows:
            return

        found = 0
        for row in rows:
            if found >= self.meta.max_items:
                return
            item = self._map_row(row)
            if item is not None:
                found += 1
                yield item

    def _map_row(self, row: dict[str, Any]) -> Item | None:
        if not self.field_map:
            raise ParseError(
                f"{type(self).__name__}.field_map kosong -- gak tau cara "
                "map JSON row ke Item. Isi field_map, atau subclass "
                "BaseScraper langsung kalau mapping-nya gak sesederhana itu."
            )
        try:
            kwargs = {field: row[key] for field, key in self.field_map.items()}
        except (KeyError, TypeError):
            return None
        return self.item_model(**kwargs)
