"""IOCRepo -- satu-satunya jalur tulis `iocs`. Gantiin dua jalur nulis
terpisah di sistem lama (`dbMongo.upsert_ioc_from_feed` sync vs
`ioc_service.upsert_ioc` async, beda kekayaan data) -- lihat plan §6.
"""

from __future__ import annotations

import datetime
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from cti_core.db.models.ioc import IOC, IOCFeedback, IOCSource, IOCTag, IOCThreatActor

_VALID_VERDICTS = frozenset({"tp", "fp"})
_VALID_TYPES = frozenset({"ip", "url", "domain", "email", "sha256", "sha1", "md5", "cve"})


class IOCRepo:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert(
        self,
        *,
        type: str,
        value: str,
        source_url: str,
        source_name: str,
        context: str | None = None,
        article_id: int | None = None,
    ) -> IOC:
        existing = self.session.execute(
            select(IOC).where(IOC.type == type, IOC.value == value)
        ).scalar_one_or_none()
        now = datetime.datetime.now(datetime.UTC)

        if existing is None:
            ioc = IOC(type=type, value=value, first_seen_at=now, last_seen_at=now, seen_count=1)
            self.session.add(ioc)
        else:
            ioc = existing
            ioc.last_seen_at = now
            ioc.seen_count += 1

        ioc.sources.append(
            IOCSource(
                url=source_url,
                source_name=source_name,
                context=context,
                article_id=article_id,
                first_seen_at=now,
            )
        )
        self.session.flush()
        return ioc

    def add_feedback(
        self, ioc: IOC, *, verdict: str, submitted_by: str, note: str | None = None
    ) -> IOC:
        if verdict not in _VALID_VERDICTS:
            raise ValueError(f"verdict '{verdict}' harus salah satu dari {_VALID_VERDICTS}")
        ioc.feedback.append(IOCFeedback(verdict=verdict, submitted_by=submitted_by, note=note))
        if verdict == "tp":
            ioc.tp_count += 1
        else:
            ioc.fp_count += 1
        self.session.flush()
        return ioc

    def get(self, *, type: str, value: str) -> IOC | None:
        return self.session.execute(
            select(IOC).where(IOC.type == type, IOC.value == value)
        ).scalar_one_or_none()


class AsyncIOCRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(
        self,
        *,
        type: str,
        value: str,
        source_url: str,
        source_name: str,
        context: str | None = None,
        article_id: int | None = None,
    ) -> IOC:
        result = await self.session.execute(select(IOC).where(IOC.type == type, IOC.value == value))
        existing = result.scalar_one_or_none()
        now = datetime.datetime.now(datetime.UTC)

        if existing is None:
            ioc = IOC(type=type, value=value, first_seen_at=now, last_seen_at=now, seen_count=1)
            self.session.add(ioc)
        else:
            ioc = existing
            ioc.last_seen_at = now
            ioc.seen_count += 1

        ioc.sources.append(
            IOCSource(
                url=source_url,
                source_name=source_name,
                context=context,
                article_id=article_id,
                first_seen_at=now,
            )
        )
        await self.session.flush()
        return ioc

    async def add_feedback(
        self, ioc: IOC, *, verdict: str, submitted_by: str, note: str | None = None
    ) -> IOC:
        if verdict not in _VALID_VERDICTS:
            raise ValueError(f"verdict '{verdict}' harus salah satu dari {_VALID_VERDICTS}")
        ioc.feedback.append(IOCFeedback(verdict=verdict, submitted_by=submitted_by, note=note))
        if verdict == "tp":
            ioc.tp_count += 1
        else:
            ioc.fp_count += 1
        await self.session.flush()
        return ioc

    async def apply_confidence_and_actionability(
        self,
        ioc: IOC,
        *,
        confidence_score: int,
        actionability_score: int,
        actionability_label: str,
        recommended_action: str,
        decayed_at: datetime.datetime,
    ) -> IOC:
        """Port bagian akhir `ioc_service.submit_feedback()` (Fase 7.4 Grup
        D) -- recompute confidence+actionability abis feedback baru masuk."""
        ioc.confidence_score = confidence_score
        ioc.confidence_decayed_at = decayed_at
        ioc.actionability_score = actionability_score
        ioc.actionability_label = actionability_label
        ioc.recommended_action = recommended_action
        await self.session.flush()
        return ioc

    async def get(self, *, type: str, value: str) -> IOC | None:
        result = await self.session.execute(select(IOC).where(IOC.type == type, IOC.value == value))
        return result.scalar_one_or_none()

    async def get_by_id(self, ioc_id: int) -> IOC | None:
        result = await self.session.execute(select(IOC).where(IOC.id == ioc_id))
        return result.scalar_one_or_none()

    async def list_first_seen_on(self, day: datetime.date, *, limit: int = 200) -> list[IOC]:
        """Port `_collect_iocs()` (`recap_service.py`, Fase 7.3 router
        `recap`, Bagian 5) -- IOC yang PERTAMA ketemu tanggal ini."""
        result = await self.session.execute(
            select(IOC)
            .where(func.date(IOC.first_seen_at) == day)
            .order_by(IOC.first_seen_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_filtered(
        self,
        *,
        page: int = 1,
        page_size: int = 50,
        ioc_type: str | None = None,
        search: str | None = None,
        tags: Sequence[str] | None = None,
        sort_by: str | None = None,
    ) -> tuple[list[IOC], int]:
        """Port `ioc_service.get_iocs()`. `actionability` (filter lama)
        SENGAJA gak diport -- itu field turunan `confidence_service`
        (skoring, ditunda bareng `articles`'s confidence -- lihat
        PROGRESS.md Fase 7.3), gak ada kolomnya di skema baru."""
        stmt = select(IOC)
        if ioc_type and ioc_type in _VALID_TYPES:
            stmt = stmt.where(IOC.type == ioc_type)
        if search:
            stmt = stmt.where(IOC.value.ilike(f"%{search}%"))
        if tags:
            stmt = stmt.join(IOC.tags).where(IOCTag.tag.in_(tags)).distinct()

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()

        order_col = IOC.confidence_score if sort_by == "confidence" else IOC.last_seen_at
        list_stmt = stmt.order_by(order_col.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(list_stmt)
        return list(result.scalars().unique().all()), total

    async def list_with_feedback(self) -> list[IOC]:
        """IOC yang punya minimal satu feedback (tp/fp) -- port filter
        `{"feedback_log": {"$exists": True, "$ne": []}}`
        (`fp_analytics_service.get_fp_analytics()`, Fase 7.4 Grup D)."""
        result = await self.session.execute(select(IOC).where(IOC.feedback.any()))
        return list(result.scalars().all())

    async def get_stats(self) -> dict[str, object]:
        total = (await self.session.execute(select(func.count()).select_from(IOC))).scalar_one()
        by_type_stmt = (
            select(IOC.type, func.count()).group_by(IOC.type).order_by(func.count().desc())
        )
        by_type = (await self.session.execute(by_type_stmt)).all()
        return {
            "total": total,
            "by_type": [{"type": t, "count": c} for t, c in by_type],
        }

    async def add_tags(self, ioc: IOC, tags: Sequence[str]) -> IOC:
        existing = {t.tag for t in ioc.tags}
        for tag in tags:
            if tag not in existing:
                ioc.tags.append(IOCTag(tag=tag))
                existing.add(tag)
        await self.session.flush()
        return ioc

    async def add_threat_actors(self, ioc: IOC, threat_actors: Sequence[str]) -> IOC:
        existing = {t.threat_actor for t in ioc.threat_actors}
        for actor in threat_actors:
            if actor not in existing:
                ioc.threat_actors.append(IOCThreatActor(threat_actor=actor))
                existing.add(actor)
        await self.session.flush()
        return ioc

    async def remove_threat_actor(self, ioc: IOC, actor: str) -> bool:
        match = next((t for t in ioc.threat_actors if t.threat_actor == actor), None)
        if match is None:
            return False
        # `.remove()` dari koleksi (bukan `session.delete()` langsung) --
        # `cascade="all, delete-orphan"` (model) yang urus DELETE pas
        # flush, DAN koleksi in-memory `ioc.threat_actors` langsung
        # ke-update tanpa staleness (lihat bug `update_client_ids`,
        # `AsyncUserRepo`, Fase 7.2 -- `session.delete()` langsung pada
        # child gak nyabut dia dari koleksi parent yang udah ke-load).
        ioc.threat_actors.remove(match)
        await self.session.flush()
        return True

    async def delete(self, ioc_id: int) -> bool:
        ioc = await self.get_by_id(ioc_id)
        if ioc is None:
            return False
        await self.session.delete(ioc)
        await self.session.flush()
        return True

    async def bulk_delete(self, ioc_ids: Sequence[int]) -> int:
        count = 0
        for ioc_id in ioc_ids:
            if await self.delete(ioc_id):
                count += 1
        return count
