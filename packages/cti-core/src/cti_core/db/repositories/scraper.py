"""ScraperRunRepo -- heartbeat per-run. Ini yang bikin run nol-item vs run
crash bisa dibedain, gantiin `scraper_health.py` 15-baris read-only yang
cuma bisa liat per-artikel (lihat plan §8.1).

Timestamp di-set EKSPLISIT di Python (bukan diserahin ke server_default lalu
dibaca balik) -- sesi async gak bisa lazy-refresh atribut yang di-expire
tanpa `await`, jadi ngandelin server_default+implicit-reload bakal
meledak diam-diam di jalur async. Server_default di model tetap ada, itu
cuma jaring pengaman kalau ada jalur lain yang insert tanpa lewat repo ini.

`ScraperItemRepo`/`ScraperConfigRepo` (Fase 9) numpang file yang sama --
tiga aggregate ini (`ScraperRun`/`ScraperItem`/`ScraperConfig`) semuanya
"satu domain: control plane scraper", gak perlu dipisah file kayak
aggregate lain yang beneran independen.
"""

from __future__ import annotations

import datetime
from typing import Any, cast

from sqlalchemy import delete, func, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from cti_core.db.models.scraper import ScraperConfig, ScraperItem, ScraperRun


class _UnsetType:
    """Sentinel tipe buat parameter `ScraperConfigRepo.upsert()` yang
    `None`-nya sendiri udah bermakna ("hapus override ini, balik ke
    default kode") -- beda dari `None` default biasa yang berarti
    "caller gak ngirim parameter ini". Diketik eksplisit ke Union (bukan
    `Any`) biar mypy `is not UNSET` narrow dengan bener."""

    def __repr__(self) -> str:
        return "UNSET"


UNSET = _UnsetType()

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
        "disabled",
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

    def list_recent_by_scraper(self, scraper_id: str, *, limit: int = 10) -> list[ScraperRun]:
        """Dipakai health sweep (Fase 9) -- N run TERAKHIR buat nentuin
        dead/degraded/zero_yield, bukan seluruh histori."""
        result = self.session.execute(
            select(ScraperRun)
            .where(ScraperRun.scraper_id == scraper_id)
            .order_by(ScraperRun.started_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


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

    async def latest_per_scraper(self) -> dict[str, ScraperRun]:
        """SATU run terbaru per `scraper_id` -- `DISTINCT ON` Postgres
        (bukan portable, tapi seluruh platform ini emang Postgres-only,
        lihat plan). Dipakai `GET /api/scraper` (list view) buat status
        kolom tanpa N+1 query per scraper."""
        result = await self.session.execute(
            select(ScraperRun)
            .distinct(ScraperRun.scraper_id)
            .order_by(ScraperRun.scraper_id, ScraperRun.started_at.desc())
        )
        return {run.scraper_id: run for run in result.scalars().all()}

    async def list_by_scraper(
        self, scraper_id: str, *, page: int = 1, page_size: int = 20
    ) -> tuple[list[ScraperRun], int]:
        total = (
            await self.session.execute(
                select(func.count())
                .select_from(ScraperRun)
                .where(ScraperRun.scraper_id == scraper_id)
            )
        ).scalar_one()
        result = await self.session.execute(
            select(ScraperRun)
            .where(ScraperRun.scraper_id == scraper_id)
            .order_by(ScraperRun.started_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def list_recent_by_scraper(self, scraper_id: str, *, limit: int = 10) -> list[ScraperRun]:
        result = await self.session.execute(
            select(ScraperRun)
            .where(ScraperRun.scraper_id == scraper_id)
            .order_by(ScraperRun.started_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


# ── ScraperItem -- log accept/reject per artikel dalam satu run ─────────────


def _item_expire_at(retention_days: int) -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=retention_days)


class ScraperItemRepo:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        run_id: str,
        scraper_id: str,
        url_hash: str,
        title: str,
        url: str,
        accepted: bool,
        reason: str | None,
        retention_days: int,
        legacy_script_label: str | None = None,
    ) -> ScraperItem:
        row = ScraperItem(
            run_id=run_id,
            scraper_id=scraper_id,
            url_hash=url_hash,
            title=title,
            url=url,
            accepted=accepted,
            reason=reason,
            legacy_script_label=legacy_script_label,
            expire_at=_item_expire_at(retention_days),
        )
        self.session.add(row)
        self.session.flush()
        return row

    def purge_expired(self) -> int:
        """Dipanggil task Celery periodik (`scraper.purge_expired_items`,
        `maintenance` queue) -- pola sama kayak `ScraperSeenRepo` (gak ada
        TTL index bawaan Postgres)."""
        now = datetime.datetime.now(datetime.UTC)
        result = cast(
            "CursorResult[Any]",
            self.session.execute(delete(ScraperItem).where(ScraperItem.expire_at < now)),
        )
        self.session.commit()
        return result.rowcount


class AsyncScraperItemRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_by_scraper(
        self,
        scraper_id: str,
        *,
        page: int = 1,
        page_size: int = 20,
        accepted: bool | None = None,
    ) -> tuple[list[ScraperItem], int]:
        stmt = select(ScraperItem).where(ScraperItem.scraper_id == scraper_id)
        count_stmt = (
            select(func.count())
            .select_from(ScraperItem)
            .where(ScraperItem.scraper_id == scraper_id)
        )
        if accepted is not None:
            stmt = stmt.where(ScraperItem.accepted == accepted)
            count_stmt = count_stmt.where(ScraperItem.accepted == accepted)
        total = (await self.session.execute(count_stmt)).scalar_one()
        result = await self.session.execute(
            stmt.order_by(ScraperItem.run_at.desc()).offset((page - 1) * page_size).limit(page_size)
        )
        return list(result.scalars().all()), total

    async def list_by_run(self, run_id: str) -> list[ScraperItem]:
        result = await self.session.execute(
            select(ScraperItem)
            .where(ScraperItem.run_id == run_id)
            .order_by(ScraperItem.run_at.asc())
        )
        return list(result.scalars().all())


# ── ScraperConfig -- SATU-SATUNYA permukaan operator boleh tulis ────────────


class ScraperConfigRepo:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, scraper_id: str) -> ScraperConfig | None:
        return self.session.get(ScraperConfig, scraper_id)

    def get_all(self) -> dict[str, ScraperConfig]:
        """Dipakai `build_beat_schedule()` -- SATU query buat semua
        override, bukan N query per scraper pas beat nyusun jadwal."""
        result = self.session.execute(select(ScraperConfig))
        return {row.scraper_id: row for row in result.scalars().all()}


class AsyncScraperConfigRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, scraper_id: str) -> ScraperConfig | None:
        return await self.session.get(ScraperConfig, scraper_id)

    async def get_all(self) -> dict[str, ScraperConfig]:
        result = await self.session.execute(select(ScraperConfig))
        return {row.scraper_id: row for row in result.scalars().all()}

    async def upsert(
        self,
        scraper_id: str,
        *,
        enabled: bool | None = None,
        schedule: str | _UnsetType | None = UNSET,
        rate_limit: str | _UnsetType | None = UNSET,
        max_items: int | _UnsetType | None = UNSET,
        paused_reason: str | _UnsetType | None = UNSET,
        updated_by: str | None = None,
    ) -> ScraperConfig:
        """`UNSET` (sentinel, BUKAN `None`) buat field opsional yang
        default-nya "jangan sentuh field ini" -- `None` itu nilai yang SAH
        buat `schedule`/`rate_limit`/`max_items`/`paused_reason` (artinya
        "hapus override, balik ke default kode"), jadi gak bisa dipakai
        double-duty sebagai "parameter ini gak dikirim caller"."""
        row = await self.get(scraper_id)
        if row is None:
            row = ScraperConfig(scraper_id=scraper_id, enabled=True)
            self.session.add(row)
        if enabled is not None:
            row.enabled = enabled
        if not isinstance(schedule, _UnsetType):
            row.schedule = schedule
        if not isinstance(rate_limit, _UnsetType):
            row.rate_limit = rate_limit
        if not isinstance(max_items, _UnsetType):
            row.max_items = max_items
        if not isinstance(paused_reason, _UnsetType):
            row.paused_reason = paused_reason
        if updated_by is not None:
            row.updated_by = updated_by
        await self.session.flush()
        return row

    async def reset(self, scraper_id: str) -> bool:
        """Hapus override sepenuhnya -- balik ke `ScraperMeta` default
        kode. Return False kalau emang gak ada override buat dihapus."""
        row = await self.get(scraper_id)
        if row is None:
            return False
        await self.session.delete(row)
        await self.session.flush()
        return True
