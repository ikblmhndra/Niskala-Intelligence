"""AsyncRecapRepo -- CRUD cache `daily_recaps`. Fase 7.3 (router `recap`,
Bagian 5). Generate-nya sendiri (kumpulin data + panggil LLM) ada di
`cti_api.services.recap`, repo ini murni persistensi."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cti_core.db.models.recap import DailyRecap


class AsyncRecapRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, date: str) -> DailyRecap | None:
        result = await self.session.execute(select(DailyRecap).where(DailyRecap.date == date))
        return result.scalar_one_or_none()

    async def list_recent(self, limit: int = 30) -> list[DailyRecap]:
        result = await self.session.execute(
            select(DailyRecap).order_by(DailyRecap.date.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def upsert(self, date: str, **fields: Any) -> DailyRecap:
        existing = await self.get(date)
        if existing is not None:
            for k, v in fields.items():
                setattr(existing, k, v)
            await self.session.flush()
            return existing
        row = DailyRecap(date=date, **fields)
        self.session.add(row)
        await self.session.flush()
        return row
