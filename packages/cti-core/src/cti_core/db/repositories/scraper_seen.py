"""ScraperSeenRepo -- primitif DB dedup two-phase, gantiin
`threatintel.offsets`. Hash `dedup_key` DIHITUNG di `cti_scraper.dedup`
(scraper_id + key mentah -> sha256), bukan di sini -- modul ini cuma
nyimpen/baca hasilnya. Lihat model `ScraperSeen` buat kenapa kolomnya
bukan `url_hash`.
"""

from __future__ import annotations

import datetime
from typing import Any, cast

from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from cti_core.db.models.scraper import ScraperSeen


class ScraperSeenRepo:
    def __init__(self, session: Session) -> None:
        self.session = session

    def try_reserve(
        self, *, dedup_key: str, scraper_id: str, lease_s: int, max_attempts: int = 5
    ) -> bool:
        """True kalau caller SEKARANG pegang reservasi ini. Empat hasil
        (lihat plan §3.3):

          - belum ada baris                    -> insert in_flight, True
          - ada, state=done atau poisoned      -> False (duplikat beneran)
          - ada, in_flight, lease masih hidup  -> False (worker lain pegang)
          - ada, in_flight, lease KADALUARSA   -> curi lease-nya, True

        Kasus terakhir itu yang bikin "mark setelah sukses" aman dari
        crash: worker yang mati di tengah proses nyisain lease basi, run
        berikutnya ambil lagi -- beda dari `is_new_and_mark` lama yang
        nge-mark SEBELUM proses dan kehilangan item itu selamanya kalau
        gagal di tengah jalan.
        """
        now = datetime.datetime.now(datetime.UTC)
        existing = self.session.get(ScraperSeen, dedup_key)

        if existing is None:
            row = ScraperSeen(
                dedup_key=dedup_key,
                scraper_id=scraper_id,
                state="in_flight",
                lease_until=now + datetime.timedelta(seconds=lease_s),
                attempts=1,
                first_seen_at=now,
                # In-flight TTL pendek -- kalau ditinggal (crash, gak pernah
                # commit/release), baris ini bersih sendiri lewat purge
                # periodik (Fase 6), gak nyangkut selamanya kayak offsets lama.
                expire_at=now + datetime.timedelta(days=1),
            )
            self.session.add(row)
            self.session.flush()
            return True

        if existing.state == "done" or existing.poisoned:
            return False

        if existing.lease_until is not None and existing.lease_until > now:
            return False  # worker lain masih pegang, belum kadaluarsa

        if existing.attempts >= max_attempts:
            existing.poisoned = True
            existing.state = "done"
            self.session.flush()
            return False

        existing.lease_until = now + datetime.timedelta(seconds=lease_s)
        existing.attempts += 1
        self.session.flush()
        return True

    def commit(self, dedup_key: str, *, ttl_days: int) -> None:
        """Dipanggil SETELAH sink sukses -- ini yang bikin dedup gak lagi
        nge-mark sebelum kerjaan kelar."""
        now = datetime.datetime.now(datetime.UTC)
        row = self.session.get(ScraperSeen, dedup_key)
        if row is None:
            return
        row.state = "done"
        row.committed_at = now
        row.expire_at = now + datetime.timedelta(days=ttl_days)
        self.session.flush()

    def release(self, dedup_key: str) -> None:
        """Sink gagal dengan cara yang worth di-retry -- hapus reservasi
        biar run berikutnya nyoba lagi dari nol, gak nunggu lease basi."""
        row = self.session.get(ScraperSeen, dedup_key)
        if row is not None:
            self.session.delete(row)
            self.session.flush()

    def has_any(self, scraper_id: str) -> bool:
        """Scraper ini punya SATU PUN baris dedup (state apa pun)? Dasar
        definisi "cold start" (Fase 10, `Runner._cold_start_cap`): scraper
        tanpa baris sama sekali = belum pernah nyimpen apa-apa, entah karena
        emang baru, atau karena `reset_scraper()`/purge TTL ngosongin semuanya.
        Sengaja BUKAN "belum pernah ada `ScraperRun`" -- scraper yang di-
        warm-start (seed `scraper_seen` dari dump lama) gak boleh kena cap,
        atau item baru sejak dump ikut kebuang."""
        row = self.session.execute(
            select(ScraperSeen.dedup_key).where(ScraperSeen.scraper_id == scraper_id).limit(1)
        ).first()
        return row is not None

    def reset_scraper(self, scraper_id: str) -> int:
        """Control plane 'lupain semuanya' (Fase 9) -- dipanggil analis
        setelah benerin parser yang sempat ngeluarin sampah. Return jumlah
        baris yang dihapus."""
        rows = (
            self.session.execute(select(ScraperSeen).where(ScraperSeen.scraper_id == scraper_id))
            .scalars()
            .all()
        )
        for row in rows:
            self.session.delete(row)
        self.session.flush()
        return len(rows)

    def purge_expired(self) -> int:
        """Dipanggil task Celery periodik `scraper.purge_expired_seen`
        (Fase 9) -- docstring model `ScraperSeen` udah nyebut task ini
        sejak Fase 3 ("Fase 6: cti.maintenance.purge_expired_seen"), tapi
        gak pernah beneran ditulis sampai sekarang (grep kosong total
        sebelum Fase 9) -- baris `expire_at`-nya lewat numpuk gak abis-abis
        dari hari pertama deploy."""
        now = datetime.datetime.now(datetime.UTC)
        result = cast(
            "CursorResult[Any]",
            self.session.execute(delete(ScraperSeen).where(ScraperSeen.expire_at < now)),
        )
        self.session.commit()
        return result.rowcount


class AsyncScraperSeenRepo:
    """Cuma `reset_scraper()` -- satu-satunya operasi yang dipanggil dari
    API (Fase 9, `POST /api/scraper/{id}/reset-dedup`). Sisa siklus hidup
    dedup (`try_reserve`/`commit`/`release`) murni internal `Runner`
    (worker, sesi sync) -- gak butuh padanan async."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def reset_scraper(self, scraper_id: str) -> int:
        result = cast(
            "CursorResult[Any]",
            await self.session.execute(
                delete(ScraperSeen).where(ScraperSeen.scraper_id == scraper_id)
            ),
        )
        await self.session.flush()
        return result.rowcount
