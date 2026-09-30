"""Pembaca dump Mongo (`mongodump` -> file BSON) buat script seed Fase 10.

Dipisah dari script-nya supaya logika seed bisa dites tanpa `pymongo`: fungsi
seed cuma minta objek dengan method `docs(nama)`, bukan file BSON. `pymongo`
(yang bawa modul `bson`) SENGAJA bukan dependency proyek -- ini alat migrasi
sekali pakai, jadi diimpor lazy dan dipasang lewat `uv run --with pymongo`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

DEFAULT_DUMP_DIR = Path(__file__).resolve().parents[2] / "legacy" / "dump"


class DumpError(RuntimeError):
    """Dump gak bisa dibaca / koleksi yang wajib ada gak ketemu."""


class Dump(Protocol):
    def docs(self, name: str) -> list[dict[str, Any]]:
        """Semua dokumen koleksi `<database>/<koleksi>`, mis. `news_db/clients`."""


class DirDump:
    """Baca `<root>/<database>/<koleksi>.bson` -- struktur keluaran `mongodump`."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def docs(self, name: str) -> list[dict[str, Any]]:
        path = self.root / f"{name}.bson"
        if not path.is_file():
            raise DumpError(f"koleksi '{name}' gak ada di dump: {path}")
        try:
            import bson
        except ImportError as e:
            raise DumpError(
                "modul `bson` gak ada -- jalankan lewat `uv run --with pymongo python ...`"
            ) from e
        return list(bson.decode_all(path.read_bytes()))


class MemoryDump:
    """Dump palsu buat test: `MemoryDump({"news_db/clients": [{...}, ...]})`.
    Koleksi yang gak dikasih dianggap kosong, bukan error -- test cuma perlu
    nyebut koleksi yang dia pedulikan."""

    def __init__(self, collections: dict[str, list[dict[str, Any]]]) -> None:
        self._collections = collections

    def docs(self, name: str) -> list[dict[str, Any]]:
        return [dict(d) for d in self._collections.get(name, [])]
