"""Auto-discovery. Taruh file scraper di bawah `cti_scrapers/`, itu doang --
gak ada file lain yang perlu diedit, gak ada entri di `pyproject.toml`
buat scraper first-party.
"""

from __future__ import annotations

import importlib
import pkgutil
import threading
from importlib.metadata import entry_points
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cti_scraper.base import BaseScraper

_REGISTRY: dict[str, type[BaseScraper]] = {}
_DISCOVERED = threading.Event()
_LOCK = threading.Lock()


class DuplicateScraperId(Exception):
    """Dua class beda deklarasi `meta.id` yang sama."""


def register(cls: type[BaseScraper]) -> None:
    """Dipanggil `BaseScraper.__init_subclass__` -- jangan panggil manual."""
    meta = cls.meta
    existing = _REGISTRY.get(meta.id)
    if existing is not None and existing is not cls:
        raise DuplicateScraperId(
            f"'{meta.id}' udah dideklarasiin di "
            f"{existing.__module__}.{existing.__qualname__}, gak boleh dipake "
            f"lagi di {cls.__module__}.{cls.__qualname__}"
        )
    _REGISTRY[meta.id] = cls


def discover(*, package: str = "cti_scrapers", force: bool = False) -> dict[str, type[BaseScraper]]:
    """Import semua modul di bawah `package` biar `__init_subclass__` jalan,
    lalu gabungin entry point pihak ketiga (grup `"cti.scrapers"`, buat
    plugin di luar monorepo).

    Idempoten -- panggilan kedua dst gak ngapa-ngapain kecuali `force=True`.
    Modul yang gagal di-import GAGAL KERAS di sini (fail loud), bukan diam-
    diam ke-skip -- ini yang nangkep kelas bug "lupa `import lxml.html`" di
    waktu CI/boot worker, bukan diam-diam mati selamanya kayak sistem lama.
    """
    with _LOCK:
        if _DISCOVERED.is_set() and not force:
            return dict(_REGISTRY)
        if force:
            _REGISTRY.clear()
            _DISCOVERED.clear()

        try:
            pkg = importlib.import_module(package)
        except ImportError:
            _DISCOVERED.set()
            return dict(_REGISTRY)

        if hasattr(pkg, "__path__"):
            for mod in pkgutil.walk_packages(pkg.__path__, prefix=f"{package}."):
                importlib.import_module(mod.name)

        for ep in entry_points(group="cti.scrapers"):
            ep.load()

        _DISCOVERED.set()
        return dict(_REGISTRY)


def get(scraper_id: str) -> type[BaseScraper]:
    discover()
    try:
        return _REGISTRY[scraper_id]
    except KeyError:
        raise KeyError(
            f"scraper '{scraper_id}' gak kedaftar. Cek: file-nya ada di bawah "
            "cti_scrapers/, class-nya subclass BaseScraper, meta.id cocok."
        ) from None


def all_scrapers(*, package: str = "cti_scrapers") -> dict[str, type[BaseScraper]]:
    return discover(package=package)


def reset() -> None:
    """Testing doang -- kosongin registry biar tiap test mulai bersih."""
    _REGISTRY.clear()
    _DISCOVERED.clear()
