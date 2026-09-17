"""IOCRepo -- satu-satunya jalur tulis `iocs`. Gantiin dua jalur nulis
terpisah di sistem lama (`dbMongo.upsert_ioc_from_feed` sync vs
`ioc_service.upsert_ioc` async, beda kekayaan data) -- lihat plan §6.
"""

from __future__ import annotations

import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from cti_core.db.models.ioc import IOC, IOCFeedback, IOCSource

_VALID_VERDICTS = frozenset({"tp", "fp"})


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

    async def get(self, *, type: str, value: str) -> IOC | None:
        result = await self.session.execute(select(IOC).where(IOC.type == type, IOC.value == value))
        return result.scalar_one_or_none()
