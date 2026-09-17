"""DedupStore -- reserve/commit/release two-phase, gantiin
`is_new_and_mark()` di `ScraperNews/modules/offsetStore.py`.

Tiga cacat desain lama yang diperbaiki di sini (lihat plan §2/§3):
  1. Ditandai SEBELUM diproses -> release() bikin item bisa dicoba ulang
     kalau sink gagal, bukan hilang permanen.
  2. Key `str(title)+str(url)` mentah -> `raw_key` yang dikasih ke sini
     harusnya udah lewat `Item.dedup_key()` (biasanya
     `cti_core.urlkit.canonicalize_url`), bukan concat mentah.
  3. Namespace campur -- di sini SENGAJA di-namespace per `scraper_id`,
     beda dari `cti_core.urlkit.url_hash()` yang identitasnya LINTAS-scraper
     (dipakai di `Article.url_hash`). Dua scraper yang liput situs sama
     harus dedup terpisah -- itu keputusan sadar, bukan kebetulan.
"""

from __future__ import annotations

import hashlib

from cti_core.db.repositories.scraper_seen import ScraperSeenRepo
from sqlalchemy.orm import Session


def compute_dedup_key(scraper_id: str, raw_key: str) -> str:
    """sha256(scraper_id + NUL + raw_key). Beda nilai dari
    `cti_core.urlkit.url_hash()` walau raw_key-nya URL yang sama persis --
    itu disengaja, lihat docstring modul."""
    return hashlib.sha256(f"{scraper_id}\x00{raw_key}".encode()).hexdigest()


class DedupStore:
    def __init__(self, session: Session, *, lease_s: int = 900) -> None:
        self._repo = ScraperSeenRepo(session)
        self._lease_s = lease_s

    def reserve(self, *, scraper_id: str, raw_key: str) -> str | None:
        """Return `dedup_key` kalau caller berhasil reserve item ini,
        `None` kalau duplikat beneran atau lease dipegang worker lain.
        Simpen return value-nya -- itu yang dipassing ke `commit()`/`release()`.
        """
        key = compute_dedup_key(scraper_id, raw_key)
        reserved = self._repo.try_reserve(
            dedup_key=key, scraper_id=scraper_id, lease_s=self._lease_s
        )
        return key if reserved else None

    def commit(self, dedup_key: str, *, ttl_days: int) -> None:
        """Panggil SETELAH sink sukses nulis. TTL berapa lama key ini
        dianggap 'udah pernah keliatan' sebelum boleh muncul lagi (situs
        dengan konten yang muter ulang mungkin butuh TTL lebih pendek)."""
        self._repo.commit(dedup_key, ttl_days=ttl_days)

    def release(self, dedup_key: str) -> None:
        """Panggil kalau sink GAGAL dengan cara yang worth di-retry --
        item ini bebas dicoba lagi run berikutnya, gak nunggu lease basi."""
        self._repo.release(dedup_key)

    def reset_scraper(self, scraper_id: str) -> int:
        return self._repo.reset_scraper(scraper_id)
