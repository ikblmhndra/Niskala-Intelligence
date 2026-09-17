"""Harness golden test. Ngasih plugin byte yang SAMA PERSIS dari fixture
Fase 0 (`tools/salvage/record_fixtures.py`), biar scraper bisa dites lawan
`expected_items.json` TANPA nyentuh jaringan sama sekali -- termasuk buat
`runtime="browser"` (lewat Playwright route interception, karena
`httpx.MockTransport` cuma ngaruh ke `ctx.http`, bukan navigasi Playwright).

Dipakai `tests/contract/test_golden.py` DAN CLI `verify` (bakal disambung
Fase 4) -- satu implementasi, dua pemakai.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
import structlog

from cti_scraper.http import ScraperHttpClient

if TYPE_CHECKING:
    from cti_scraper.base import BaseScraper, ScrapeContext
    from cti_scraper.items import Item

_CONTENT_TYPES = {
    ".xml": "application/xml",
    ".html": "text/html; charset=utf-8",
    ".json": "application/json",
}


class FixtureNotFound(Exception):
    """Fixture Fase 0 gak ketemu, atau scraper gak punya `legacy_script`
    buat nunjuk ke fixture mana."""


@dataclass
class Fixture:
    scraper_id: str
    legacy_script: str
    day: str
    """Hari (ISO date) fixture ini direkam -- dipakai juga sebagai
    `ctx.now` biar `posted_on` scraper yang pakai waktu-scrape (bukan
    tanggal artikel asli) ketemu nilai yang sama kayak waktu direkam."""
    input_files: list[Path]
    expected_items: list[dict[str, Any]]

    @property
    def primary_body(self) -> bytes:
        return self.input_files[0].read_bytes()

    @property
    def primary_content_type(self) -> str:
        return _CONTENT_TYPES.get(self.input_files[0].suffix, "application/octet-stream")


def load_fixture(fixtures_dir: Path, legacy_script: str, scraper_id: str) -> Fixture:
    d = fixtures_dir / legacy_script
    if not d.exists():
        raise FixtureNotFound(f"gak ada direktori fixture: {d}")

    expected_path = d / "expected_items.json"
    if not expected_path.exists():
        raise FixtureNotFound(f"gak ada expected_items.json di {d}")

    all_days: dict[str, list[dict[str, Any]]] = json.loads(expected_path.read_text())
    days_with_data = sorted(k for k, v in all_days.items() if v)
    if not days_with_data:
        raise FixtureNotFound(f"expected_items.json di {d} gak punya item di hari manapun")

    day = days_with_data[-1]  # hari terbaru yang punya data
    input_files = sorted(d.glob(f"{day}.input*"))
    if not input_files:
        raise FixtureNotFound(f"gak ada file '{day}.input*' di {d}")

    return Fixture(
        scraper_id=scraper_id,
        legacy_script=legacy_script,
        day=day,
        input_files=input_files,
        expected_items=all_days[day],
    )


def _build_http_transport(fixture: Fixture) -> httpx.MockTransport:
    """Semua request lewat `ctx.http` dibalikin byte fixture yang sama,
    apa pun URL-nya -- cukup buat scraper yang mukul satu URL/API (kelima
    referensi Fase 3 begitu; scraper multi-URL butuh transport per-URL,
    belum dibutuhin sampai sekarang)."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=fixture.primary_body,
            headers={"Content-Type": fixture.primary_content_type},
        )

    return httpx.MockTransport(handler)


def _build_page_route_handler(fixture: Fixture) -> Any:
    """Buat `ScrapeContext.route_handler` -- request Playwright dijawab
    lewat `page.route()`, jalur yang SAMA SEKALI beda dari httpx, itu
    kenapa `MockTransport` gak cukup buat runtime='browser'."""
    body = fixture.primary_body
    content_type = fixture.primary_content_type

    def handler(route: Any) -> None:
        route.fulfill(status=200, content_type=content_type, body=body)

    return handler


def make_fixture_context(
    scraper_cls: type[BaseScraper],
    *,
    fixtures_dir: Path,
    run_id: str = "golden-test",
) -> tuple[ScrapeContext, Fixture]:
    """`ScrapeContext` yang byte-nya dari fixture Fase 0, siap dikasih ke
    `scraper_cls().fetch(ctx)` LANGSUNG -- golden test ngetes PARSING,
    bukan dedup/sink/heartbeat (itu urusan `runner.Runner`, diuji terpisah)."""
    from cti_scraper.base import ScrapeContext  # local -- hindari cycle base<->testing

    meta = scraper_cls.meta
    if not meta.legacy_script:
        raise FixtureNotFound(
            f"scraper '{meta.id}' gak punya meta.legacy_script -- gak tau "
            "fixture Fase 0 mana yang harus dipakai"
        )
    fixture = load_fixture(fixtures_dir, meta.legacy_script, meta.id)

    log = structlog.get_logger(scraper_id=meta.id, run_id=run_id, golden_test=True)
    now = datetime.fromisoformat(fixture.day).replace(tzinfo=UTC)

    if meta.runtime == "browser":
        http = ScraperHttpClient(timeout_s=meta.timeout_s, rate_limit=meta.rate_limit)
        ctx = ScrapeContext(meta=meta, run_id=run_id, http=http, log=log, now=now)
        ctx.route_handler = _build_page_route_handler(fixture)
    else:
        transport = _build_http_transport(fixture)
        http = ScraperHttpClient(
            timeout_s=meta.timeout_s, rate_limit=meta.rate_limit, transport=transport
        )
        ctx = ScrapeContext(meta=meta, run_id=run_id, http=http, log=log, now=now)

    return ctx, fixture


def article_keys(items: list[Item]) -> set[tuple[str, str, str]]:
    """(title, url, posted_on-ISO) -- perbandingan default buat ArticleItem."""
    return {
        (i.title, i.url, i.posted_on.isoformat() if i.posted_on else "")  # type: ignore[attr-defined]
        for i in items
    }


def expected_article_keys(expected: list[dict[str, Any]]) -> set[tuple[str, str, str]]:
    return {(e["title"], e["url"], e.get("posted_on", "")) for e in expected}


def dedup_keys(items: list[Item]) -> set[str]:
    """Perbandingan buat item non-artikel (mis. RansomwareVictimItem) --
    bandingin IDENTITAS, bukan seluruh field. Lihat KNOWN_BROKEN.md soal
    kenapa full-dict gak bisa dipakai: harness perekam Fase 0
    nge-stringify semua value (`None` jadi string `"None"`), jadi
    perbandingan field-per-field bakal false-negative buat kuirk
    perekamnya sendiri, bukan bug scraper."""
    return {k for i in items if (k := i.dedup_key()) is not None}


def normalize_ransomware_offset_key(key: str, *, prefix_fields: int = 4) -> str:
    """Fixture Fase 0 nyimpen tanggal kadang bentuk "YYYY-MM-DD", kadang
    "YYYY-MM-DD HH:MM:SS.ffffff" tergantung data mentah `ransomware.live`
    (scraper lama `str(...).split('T')[0]` gak nolongin kalau separatornya
    spasi, bukan "T"). `RansomwareVictimItem.published` di sini di-tipe
    `date` (Pydantic ngebersihin ke tanggal doang, disengaja -- ini
    perbaikan, bukan bug), jadi identitas hasil scraper baru selalu bentuk
    tanggal bersih. Normalisasi ini nyamain dua bentuk itu buat golden
    test, TANPA meniru ke-berantakan lama sebagai field bertipe `date`.

    Gak bisa pakai `rpartition(':')` polos -- komponen JAM di dalam
    tanggal berantakan ITU SENDIRI punya titik dua ("00:00:00"), jadi
    kepotong di tempat yang salah. Makanya split di N kolon PERTAMA."""
    parts = key.split(":", prefix_fields)
    date_part = parts[prefix_fields].strip().split(" ")[0]
    return ":".join((*parts[:prefix_fields], date_part))
