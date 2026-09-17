"""ScraperRunRepo -- heartbeat per-run. Ini yang bikin run nol-item vs run
crash bisa dibedain, gantiin `scraper_health.py` 15-baris read-only yang
cuma bisa liat per-artikel (lihat plan §8.1).

Timestamp di-set EKSPLISIT di Python (bukan diserahin ke server_default lalu
dibaca balik) -- sesi async gak bisa lazy-refresh atribut yang di-expire
tanpa `await`, jadi ngandelin server_default+implicit-reload bakal
meledak diam-diam di jalur async. Server_default di model tetap ada, itu
cuma jaring pengaman kalau ada jalur lain yang insert tanpa lewat repo ini.
"""

from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from cti_core.db.models.scraper import ScraperRun

_TERMINAL_STATUSES = frozenset(
    {
        "ok",
        "empty",
        "partial",
        "fetch_error",
        "parse_error",
        "rate_limited",
        "timeout",
        "backpressure",
    }
)


def _finish_fields(
    run: ScraperRun,
    *,
    status: str,
    items_found: int,
    items_new: int,
    items_dropped: int,
    items_failed: int,
    errors: list[dict[str, Any]] | None,
) -> None:
    if status not in _TERMINAL_STATUSES:
        raise ValueError(
            f"status '{status}' bukan status terminal yang dikenal: {_TERMINAL_STATUSES}"
        )
    now = datetime.datetime.now(datetime.UTC)
    run.status = status
    run.finished_at = now
    run.duration_ms = int((now - run.started_at).total_seconds() * 1000)
    run.items_found = items_found
    run.items_new = items_new
    run.items_dropped = items_dropped
    run.items_failed = items_failed
    run.errors = errors or []


class ScraperRunRepo:
    def __init__(self, session: Session) -> None:
        self.session = session

    def start(
        self,
        *,
        run_id: str,
        scraper_id: str,
        trigger: str = "beat",
        celery_task_id: str | None = None,
        worker: str | None = None,
        attempt: int = 1,
    ) -> ScraperRun:
        run = ScraperRun(
            run_id=run_id,
            scraper_id=scraper_id,
            trigger=trigger,
            status="running",
            started_at=datetime.datetime.now(datetime.UTC),
            celery_task_id=celery_task_id,
            worker=worker,
            attempt=attempt,
        )
        self.session.add(run)
        self.session.flush()
        return run

    def finish(
        self,
        run: ScraperRun,
        *,
        status: str,
        items_found: int = 0,
        items_new: int = 0,
        items_dropped: int = 0,
        items_failed: int = 0,
        errors: list[dict[str, Any]] | None = None,
    ) -> ScraperRun:
        _finish_fields(
            run,
            status=status,
            items_found=items_found,
            items_new=items_new,
            items_dropped=items_dropped,
            items_failed=items_failed,
            errors=errors,
        )
        self.session.flush()
        return run

    def get_by_run_id(self, run_id: str) -> ScraperRun | None:
        return self.session.execute(
            select(ScraperRun).where(ScraperRun.run_id == run_id)
        ).scalar_one_or_none()


class AsyncScraperRunRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def start(
        self,
        *,
        run_id: str,
        scraper_id: str,
        trigger: str = "beat",
        celery_task_id: str | None = None,
        worker: str | None = None,
        attempt: int = 1,
    ) -> ScraperRun:
        run = ScraperRun(
            run_id=run_id,
            scraper_id=scraper_id,
            trigger=trigger,
            status="running",
            started_at=datetime.datetime.now(datetime.UTC),
            celery_task_id=celery_task_id,
            worker=worker,
            attempt=attempt,
        )
        self.session.add(run)
        await self.session.flush()
        return run

    async def finish(
        self,
        run: ScraperRun,
        *,
        status: str,
        items_found: int = 0,
        items_new: int = 0,
        items_dropped: int = 0,
        items_failed: int = 0,
        errors: list[dict[str, Any]] | None = None,
    ) -> ScraperRun:
        _finish_fields(
            run,
            status=status,
            items_found=items_found,
            items_new=items_new,
            items_dropped=items_dropped,
            items_failed=items_failed,
            errors=errors,
        )
        await self.session.flush()
        return run

    async def get_by_run_id(self, run_id: str) -> ScraperRun | None:
        result = await self.session.execute(select(ScraperRun).where(ScraperRun.run_id == run_id))
        return result.scalar_one_or_none()
