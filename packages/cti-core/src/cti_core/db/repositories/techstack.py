"""AsyncTechStackRepo -- CRUD inti `techstack_entries` (Fase 2). Pola "web
kurasi, scraper patuh" -- `cti_scraper.reference_data`/`cti_enrich.stages.
score` UDAH baca tabel ini (Fase 3/4/5, live), router ini yang jadi jalur
admin buat ngisi/ubah datanya.

**Sengaja gak diport ke sini** (tetap di `techstack_service.py` lama buat
sekarang, nyusul bareng `cve.py`): backfill CVE dari client lain
(`_backfill_cves_for_tech`), trigger fetch historis NVD/MITRE
(`backfill_nvd_for_tech`/`_fetch_nvd_cves`/`_fetch_mitre_details`), dan
cascade-delete CVE pas tech dihapus (`delete_techstack` lama) -- semua itu
NULIS ke `cve_tracker` (`CveTrackerRepo`, plan §7.3 cve.py), bukan tanggung
jawab tabel `techstack_entries` sendiri. Router ini murni CRUD daftar tech
stack, gak nyentuh CVE sama sekali.

`_client_filter` Mongo lama punya fallback OR (`client_id == "default"`
ATAU field gak ada sama sekali) -- itu kompat data lama pra-multi-tenant.
Skema Postgres `client_id` NOT NULL (FK ke `clients`) sejak awal, kasus
"field gak ada" gak mungkin kejadian -- filter langsung `== client_id`,
gak perlu fallback."""

from __future__ import annotations

import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from cti_core.db.models.techstack import TechStackEntry

_VALID_EXPOSURE = frozenset({"public", "internal", "both"})
_VALID_HOSTING = frozenset({"on_prem", "cloud", "saas"})
_SORT_FIELDS = {
    "name": TechStackEntry.name,
    "added_date": TechStackEntry.added_date,
    "source": TechStackEntry.source,
    "exposure": TechStackEntry.exposure,
    "hosting_type": TechStackEntry.hosting_type,
}


class AsyncTechStackRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_filtered(
        self,
        *,
        client_id: str,
        search: str | None = None,
        page: int = 1,
        page_size: int = 50,
        sort_by: str = "name",
        sort_dir: str = "asc",
    ) -> tuple[list[TechStackEntry], int]:
        stmt = select(TechStackEntry).where(TechStackEntry.client_id == client_id)
        if search:
            stmt = stmt.where(TechStackEntry.name.ilike(f"%{search}%"))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()

        order_col = _SORT_FIELDS.get(sort_by, TechStackEntry.name)
        order = order_col.desc() if sort_dir == "desc" else order_col.asc()
        list_stmt = stmt.order_by(order).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(list_stmt)
        return list(result.scalars().all()), total

    async def get_by_name_ci(self, name: str, client_id: str) -> TechStackEntry | None:
        result = await self.session.execute(
            select(TechStackEntry).where(
                func.lower(TechStackEntry.name) == name.lower(),
                TechStackEntry.client_id == client_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, tech_id: int, client_id: str) -> TechStackEntry | None:
        result = await self.session.execute(
            select(TechStackEntry).where(
                TechStackEntry.id == tech_id, TechStackEntry.client_id == client_id
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        name: str,
        client_id: str,
        exposure: str = "internal",
        hosting_type: str = "on_prem",
    ) -> tuple[TechStackEntry | None, str]:
        """`(None, "duplicate")` kalau nama udah ada (case-insensitive) buat
        client ini -- port perilaku `add_techstack()` lama, bukan raise."""
        if await self.get_by_name_ci(name, client_id) is not None:
            return None, "duplicate"
        entry = TechStackEntry(
            name=name,
            client_id=client_id,
            exposure=exposure if exposure in _VALID_EXPOSURE else "internal",
            hosting_type=hosting_type if hosting_type in _VALID_HOSTING else "on_prem",
            source="manual",
            added_date=datetime.date.today(),
        )
        self.session.add(entry)
        await self.session.flush()
        return entry, "ok"

    async def update_exposure(self, tech_id: int, exposure: str, client_id: str) -> bool:
        if exposure not in _VALID_EXPOSURE:
            return False
        entry = await self.get_by_id(tech_id, client_id)
        if entry is None:
            return False
        entry.exposure = exposure
        await self.session.flush()
        return True

    async def update_hosting(self, tech_id: int, hosting_type: str, client_id: str) -> bool:
        if hosting_type not in _VALID_HOSTING:
            return False
        entry = await self.get_by_id(tech_id, client_id)
        if entry is None:
            return False
        entry.hosting_type = hosting_type
        await self.session.flush()
        return True

    async def delete(self, tech_id: int, client_id: str) -> bool:
        entry = await self.get_by_id(tech_id, client_id)
        if entry is None:
            return False
        await self.session.delete(entry)
        await self.session.flush()
        return True

    async def get_risk_context(self, client_id: str) -> dict[str, dict[str, str]]:
        """`{name_lower: {exposure, hosting_type}}` -- port `get_tech_risk_context()`,
        dipakai `cve.py` (nyusul) buat `adjusted_risk_score`."""
        result = await self.session.execute(
            select(TechStackEntry).where(TechStackEntry.client_id == client_id)
        )
        return {
            e.name.lower(): {
                "exposure": e.exposure or "internal",
                "hosting_type": e.hosting_type or "on_prem",
            }
            for e in result.scalars().all()
        }
