"""AsyncRFIRepo -- CRUD `rfi_requests` (Fase 7.3, Bagian 2). Port dari
`ScraperNewsWeb/app/services/rfi_service.py`. Client filter langsung
`== client_id` (skema baru NOT NULL FK dari awal) -- gak butuh fallback
OR ("default" ATAU field gak ada) kayak Mongo lama, sama pola yang udah
dipakai `AsyncTechStackRepo`.

**Asimetri client-scoping port apa adanya dari kode lama, BUKAN
keputusan baru:** `list_rfis`/`get_rfi`/`create_rfi` di-filter client_id,
tapi `update_rfi`/`delete_rfi` lama SAMA SEKALI gak nerima/nge-filter
client_id (`rfi_service.py` asli, fungsi `update_rfi(rfi_id, updates)`
dan `delete_rfi(rfi_id)` -- router-nya juga gak manggil
`effective_client_id` buat dua endpoint itu). Efeknya: siapa pun yang
tahu ID RFI bisa update/delete lintas client. Dipertahankan sesuai
instruksi "port apa adanya, flag asimetri, jangan diam-diam diperbaiki"
-- lihat juga pola sama di `articles.py`/`filtered_articles.py`."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from cti_core.db.models.rfi import RFIRequest


class AsyncRFIRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_filtered(
        self,
        *,
        client_id: str,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[RFIRequest], int]:
        stmt = select(RFIRequest).where(RFIRequest.client_id == client_id)
        if status:
            stmt = stmt.where(RFIRequest.status == status)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()

        list_stmt = (
            stmt.order_by(RFIRequest.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(list_stmt)
        return list(result.scalars().all()), total

    async def get_by_id(self, rfi_id: int, client_id: str) -> RFIRequest | None:
        result = await self.session.execute(
            select(RFIRequest).where(RFIRequest.id == rfi_id, RFIRequest.client_id == client_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_unscoped(self, rfi_id: int) -> RFIRequest | None:
        """Dipakai `update`/`delete` -- legacy gak nge-filter client_id di
        sana, lihat docstring modul."""
        result = await self.session.execute(select(RFIRequest).where(RFIRequest.id == rfi_id))
        return result.scalar_one_or_none()

    async def create(self, data: dict[str, Any], *, client_id: str) -> RFIRequest:
        rfi = RFIRequest(
            requester=data["requester"],
            question=data["question"],
            due_date=data.get("due_date"),
            status=data.get("status") or "open",
            linked_pir_id=data.get("linked_pir"),
            response=data.get("response") or "",
            client_id=client_id,
        )
        self.session.add(rfi)
        await self.session.flush()
        return rfi

    async def update(self, rfi_id: int, updates: dict[str, Any]) -> RFIRequest | None:
        rfi = await self.get_by_id_unscoped(rfi_id)
        if rfi is None:
            return None
        for key in ("requester", "question", "due_date", "status", "response"):
            if key in updates:
                setattr(rfi, key, updates[key])
        if "linked_pir" in updates:
            rfi.linked_pir_id = updates["linked_pir"]
        await self.session.flush()
        return rfi

    async def delete(self, rfi_id: int) -> bool:
        rfi = await self.get_by_id_unscoped(rfi_id)
        if rfi is None:
            return False
        await self.session.delete(rfi)
        await self.session.flush()
        return True
