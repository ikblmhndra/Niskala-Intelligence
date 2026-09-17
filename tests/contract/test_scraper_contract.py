"""Contract test -- jalan otomatis buat SEMUA scraper yang kedaftar, gak
peduli siapa yang nulis atau kapan ditambahin. Import `cti_scrapers`
gagal = test ini gagal, itu yang nangkep kelas bug
`securityaffairsThreat.py` (lupa import) di CI, bukan diam-diam mati
selamanya kayak sistem lama.
"""

from __future__ import annotations

import inspect

import croniter
import pytest
from cti_scraper.base import BaseScraper
from cti_scraper.registry import discover


@pytest.fixture(scope="module")
def registry() -> dict[str, type[BaseScraper]]:
    scrapers = discover()
    assert scrapers, (
        "gak ada scraper kedaftar -- cek cti_scrapers/ ada isinya, dan modulnya ke-import"
    )
    return scrapers


def test_at_least_five_reference_scrapers_registered(
    registry: dict[str, type[BaseScraper]],
) -> None:
    """Exit criteria Fase 3."""
    assert len(registry) >= 5


def _ids() -> list[str]:
    return sorted(discover().keys())


@pytest.mark.parametrize("scraper_id", _ids())
class TestEveryScraperConforms:
    def test_meta_id_matches_registry_key(
        self, scraper_id: str, registry: dict[str, type[BaseScraper]]
    ) -> None:
        assert registry[scraper_id].meta.id == scraper_id

    def test_schedule_is_valid_cron(
        self, scraper_id: str, registry: dict[str, type[BaseScraper]]
    ) -> None:
        cls = registry[scraper_id]
        assert croniter.croniter.is_valid(cls.meta.schedule), (
            f"'{scraper_id}': jadwal '{cls.meta.schedule}' bukan cron yang valid"
        )

    def test_fetch_is_a_generator_function(
        self, scraper_id: str, registry: dict[str, type[BaseScraper]]
    ) -> None:
        cls = registry[scraper_id]
        assert inspect.isgeneratorfunction(cls.fetch), (
            f"'{scraper_id}'.fetch() harus generator (pakai `yield`), bukan `return list`"
        )

    def test_max_items_is_bounded(
        self, scraper_id: str, registry: dict[str, type[BaseScraper]]
    ) -> None:
        """Batas keras -- parser yang tiba-tiba nge-yield ribuan item
        (bug, atau situs berubah format) gak boleh bisa banjirin queue."""
        cls = registry[scraper_id]
        assert 0 < cls.meta.max_items <= 1000

    def test_runtime_browser_scrapers_declare_it_explicitly(
        self, scraper_id: str, registry: dict[str, type[BaseScraper]]
    ) -> None:
        cls = registry[scraper_id]
        assert cls.meta.runtime in ("light", "browser")
