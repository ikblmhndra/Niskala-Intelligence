"""Golden test -- exit criteria Fase 3: 5 scraper referensi lolos lawan
fixture Fase 0. Byte HTTP/HTML PERSIS dari perekaman asli (lihat
cti_scraper.testing), bukan disimulasikan.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from cti_scraper.registry import discover
from cti_scraper.testing import (
    article_keys,
    dedup_keys,
    expected_article_keys,
    make_fixture_context,
    normalize_ransomware_offset_key,
)

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture(autouse=True, scope="module")
def _discovered() -> None:
    discover()


@pytest.mark.parametrize(
    "scraper_id",
    ["bitdefender", "cyfirma", "cisa_kev"],  # runtime="light", gak butuh Chromium
)
def test_golden_light(scraper_id: str) -> None:
    from cti_scraper.registry import get

    cls = get(scraper_id)
    ctx, fixture = make_fixture_context(cls, fixtures_dir=FIXTURES_DIR)
    items = list(cls().fetch(ctx))

    assert article_keys(items) == expected_article_keys(fixture.expected_items)


@pytest.mark.playwright
def test_golden_trendmicro() -> None:
    pytest.importorskip("playwright", reason="butuh playwright buat scraper runtime='browser'")
    from cti_scraper.registry import get

    cls = get("trendmicro")
    ctx, fixture = make_fixture_context(cls, fixtures_dir=FIXTURES_DIR)
    items = list(cls().fetch(ctx))

    assert article_keys(items) == expected_article_keys(fixture.expected_items)


def test_golden_ransomware_live() -> None:
    """Bandingin dedup_key(), bukan full-dict -- lihat docstring
    `cti_scraper.testing.dedup_keys` soal kuirk stringify di harness Fase 0.
    Tanggal dinormalisasi (`normalize_ransomware_offset_key`) karena
    `published` di sini bertipe `date` bersih -- fixture lama kadang nyimpen
    "YYYY-MM-DD HH:MM:SS.ffffff" mentah, itu perbaikan disengaja bukan bug."""
    from cti_scraper.registry import get

    cls = get("ransomware_live")
    ctx, fixture = make_fixture_context(cls, fixtures_dir=FIXTURES_DIR)
    items = list(cls().fetch(ctx))

    produced = {normalize_ransomware_offset_key(k) for k in dedup_keys(items)}
    expected = {normalize_ransomware_offset_key(e["offset_key"]) for e in fixture.expected_items}
    assert produced == expected
