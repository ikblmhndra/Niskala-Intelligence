"""Control plane scraper (Fase 9) -- BUKAN port dari legacy, `scraper.js`
lama cuma 2 widget monitoring read-only (survei Fase 8, gap #8: "Fase 9
GAK PUNYA preseden kode buat di-port -- desain dari nol"). Read (list/
detail/runs/items) kebuka buat semua user login, trigger/dry-run admin-
only -- keduanya efek nyata (trigger beneran jalanin scraper produksi,
dry-run mukul situs eksternal asli), beda dari widget monitoring pasif.

`GET /api/scraper` enumerasi `cti_scraper.registry.discover()` (84
scraper) DIGABUNG `ScraperConfig` (override) + run terakhir per scraper
(`AsyncScraperRunRepo.latest_per_scraper()`, SATU query `DISTINCT ON`,
bukan N+1). H3 (belum) nambahin enable/disable/schedule/reset-dedup +
health sweep di atas fondasi yang sama."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from cti_core.celery_client import get_celery_client
from cti_core.db.repositories.auth import AsyncAuditLogRepo
from cti_core.db.repositories.scraper import (
    AsyncScraperConfigRepo,
    AsyncScraperItemRepo,
    AsyncScraperRunRepo,
)
from cti_scraper.queues import queue_for
from cti_scraper.registry import discover
from cti_scraper.registry import get as get_scraper_cls
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from cti_core.db.models.scraper import ScraperConfig, ScraperItem, ScraperRun

from cti_api.deps import AuthedUser, get_db, request_ip, require_admin, require_auth
from cti_api.schemas.scraper import (
    ScraperConfigOut,
    ScraperDetail,
    ScraperDryRunResult,
    ScraperItemListResponse,
    ScraperItemOut,
    ScraperListItem,
    ScraperListResponse,
    ScraperRunListResponse,
    ScraperRunOut,
    ScraperTriggerResult,
)

router = APIRouter(prefix="/api/scraper", tags=["scraper"], dependencies=[Depends(require_auth)])


def _config_out(config: ScraperConfig | None, default_enabled: bool) -> ScraperConfigOut:
    if config is None:
        return ScraperConfigOut(
            enabled=default_enabled,
            schedule=None,
            rate_limit=None,
            max_items=None,
            paused_reason=None,
            updated_by=None,
            updated_at=None,
        )
    return ScraperConfigOut(
        enabled=config.enabled,
        schedule=config.schedule,
        rate_limit=config.rate_limit,
        max_items=config.max_items,
        paused_reason=config.paused_reason,
        updated_by=config.updated_by,
        updated_at=config.updated_at.isoformat() if config.updated_at else None,
    )


def _run_out(run: ScraperRun) -> ScraperRunOut:
    return ScraperRunOut(
        run_id=run.run_id,
        scraper_id=run.scraper_id,
        trigger=run.trigger,
        status=run.status,
        started_at=run.started_at.isoformat(),
        finished_at=run.finished_at.isoformat() if run.finished_at else None,
        duration_ms=run.duration_ms,
        items_found=run.items_found,
        items_new=run.items_new,
        items_dropped=run.items_dropped,
        items_failed=run.items_failed,
        errors=run.errors,
        celery_task_id=run.celery_task_id,
    )


def _item_out(row: ScraperItem) -> ScraperItemOut:
    return ScraperItemOut(
        id=row.id,
        run_id=row.run_id,
        title=row.title,
        url=row.url,
        accepted=row.accepted,
        reason=row.reason,
        run_at=row.run_at.isoformat(),
    )


@router.get("", response_model=ScraperListResponse)
async def list_scrapers(session: AsyncSession = Depends(get_db)) -> ScraperListResponse:
    registry = discover()
    configs = await AsyncScraperConfigRepo(session).get_all()
    latest_runs = await AsyncScraperRunRepo(session).latest_per_scraper()

    items: list[ScraperListItem] = []
    for scraper_id, cls in sorted(registry.items()):
        meta = cls.meta
        config = configs.get(scraper_id)
        run = latest_runs.get(scraper_id)
        items.append(
            ScraperListItem(
                id=meta.id,
                source=meta.source,
                runtime=meta.runtime,
                queue=queue_for(meta),
                tags=list(meta.tags),
                enabled=config.enabled if config is not None else meta.enabled,
                schedule=(
                    config.schedule if config is not None and config.schedule else meta.schedule
                ),
                has_override=config is not None,
                last_run_id=run.run_id if run else None,
                last_status=run.status if run else None,
                last_trigger=run.trigger if run else None,
                last_started_at=run.started_at.isoformat() if run else None,
                last_finished_at=run.finished_at.isoformat() if run and run.finished_at else None,
                last_items_found=run.items_found if run else None,
                last_items_new=run.items_new if run else None,
            )
        )
    return ScraperListResponse(scrapers=items, total=len(items))


@router.get("/{scraper_id}", response_model=ScraperDetail)
async def get_scraper(scraper_id: str, session: AsyncSession = Depends(get_db)) -> ScraperDetail:
    try:
        cls = get_scraper_cls(scraper_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="scraper not found") from None
    meta = cls.meta
    config = await AsyncScraperConfigRepo(session).get(scraper_id)
    return ScraperDetail(
        id=meta.id,
        source=meta.source,
        runtime=meta.runtime,
        credential=meta.credential,
        reference_data=list(meta.reference_data),
        tags=list(meta.tags),
        notes=meta.notes,
        default_schedule=meta.schedule,
        default_rate_limit=meta.rate_limit,
        default_max_items=meta.max_items,
        default_enabled=meta.enabled,
        default_timeout_s=meta.timeout_s,
        default_max_retries=meta.max_retries,
        default_dedup_ttl_days=meta.dedup_ttl_days,
        queue=queue_for(meta),
        config=_config_out(config, meta.enabled),
    )


@router.get("/{scraper_id}/runs", response_model=ScraperRunListResponse)
async def list_runs(
    scraper_id: str,
    page: int = 1,
    page_size: int = 20,
    session: AsyncSession = Depends(get_db),
) -> ScraperRunListResponse:
    try:
        get_scraper_cls(scraper_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="scraper not found") from None
    runs, total = await AsyncScraperRunRepo(session).list_by_scraper(
        scraper_id, page=page, page_size=page_size
    )
    return ScraperRunListResponse(
        runs=[_run_out(r) for r in runs], total=total, page=page, page_size=page_size
    )


@router.get("/{scraper_id}/items", response_model=ScraperItemListResponse)
async def list_items(
    scraper_id: str,
    page: int = 1,
    page_size: int = 20,
    accepted: bool | None = None,
    session: AsyncSession = Depends(get_db),
) -> ScraperItemListResponse:
    try:
        get_scraper_cls(scraper_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="scraper not found") from None
    rows, total = await AsyncScraperItemRepo(session).list_by_scraper(
        scraper_id, page=page, page_size=page_size, accepted=accepted
    )
    return ScraperItemListResponse(
        items=[_item_out(r) for r in rows], total=total, page=page, page_size=page_size
    )


@router.post("/{scraper_id}/trigger", response_model=ScraperTriggerResult)
async def trigger_scraper(
    scraper_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db),
    admin: AuthedUser = Depends(require_admin),
) -> ScraperTriggerResult:
    try:
        cls = get_scraper_cls(scraper_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="scraper not found") from None
    queue = queue_for(cls.meta)
    async_result = get_celery_client().send_task(
        "scrape.run", args=(scraper_id,), kwargs={"trigger": "manual"}, queue=queue
    )
    await AsyncAuditLogRepo(session).write(
        username=admin["username"],
        action="trigger_scraper",
        target_id=scraper_id,
        detail={"queue": queue, "celery_task_id": async_result.id},
        ip_address=request_ip(request),
    )
    await session.commit()
    return ScraperTriggerResult(
        scraper_id=scraper_id, celery_task_id=async_result.id, trigger="manual", queue=queue
    )


@router.post("/{scraper_id}/dry-run", response_model=ScraperDryRunResult)
async def dry_run_scraper(
    scraper_id: str,
    admin: AuthedUser = Depends(require_admin),
) -> ScraperDryRunResult:
    try:
        cls = get_scraper_cls(scraper_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="scraper not found") from None

    def _run() -> tuple[str, int, int, list[dict[str, str]]]:
        from cti_scraper.runner import Runner

        if cls.meta.reference_data:
            from cti_core.db.engine import sync_session

            with sync_session() as sync_sess:
                result = Runner(cls, session=sync_sess, dry_run=True).execute(trigger="manual")
        else:
            result = Runner(cls, dry_run=True).execute(trigger="manual")
        return result.status, result.items_found, result.duration_ms, result.errors

    # `Runner.execute()` SINKRON (HTTP/Playwright blocking) -- `to_thread`
    # biar gak nge-block event loop uvicorn selama scraper browser yang
    # lambat jalan (bisa puluhan detik).
    status, items_found, duration_ms, errors = await asyncio.to_thread(_run)
    return ScraperDryRunResult(
        scraper_id=scraper_id,
        status=status,
        items_found=items_found,
        duration_ms=duration_ms,
        errors=errors,
    )
