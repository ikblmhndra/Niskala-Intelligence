"""Port CRUD-baca + false-positive dari `ScraperNewsWeb/app/routers/cve.py`.

**Belum diport** (nyusul terpisah, masing-masing punya alasan beda):
`GET /export` (Excel, `cve_export_service` + openpyxl, belum dependency
`cti-api`), `POST /draft-email` (`cve_email_service`, Graph/email),
`POST /cisa-lookup`/`/epss-lookup`/`/exploit-lookup` (lookup API eksternal,
CISA/FIRST.org/exploit-db), `GET /{id}/mindmap` (`mermaid_service`,
generate diagram), `GET /prioritize` (`cve_priority_service`, konsep
"campaign" yang belum ada modelnya). `GET /{id}/ticket`+`PUT`,
`POST /{id}/acknowledge`+`/bulk-acknowledge`, `GET /next-ticket-id`+
`/ack-statuses`, parameter `ack_filter` di list/stats -- SEMUA nempel
konsep ticket yang skemanya (`CveTicket`/`CveTicketItem`, Fase 2) beda
desain total dari kebutuhan lama (lihat docstring `cti_core.db.
repositories.cve`), butuh keputusan desain sendiri sebelum diport."""

from __future__ import annotations

import datetime

from cti_core.db.models.cve import CveTracker
from cti_core.db.repositories.auth import AsyncAuditLogRepo
from cti_core.db.repositories.cve import AsyncCveFalsePositiveRepo, AsyncCveTrackerRepo
from cti_core.db.repositories.techstack import AsyncTechStackRepo
from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from cti_api.deps import AuthedUser, effective_client_id, get_db, request_ip, require_auth
from cti_api.schemas.cve import (
    BulkFalsePositiveBody,
    CveListResponse,
    CveOut,
    CvePocOut,
    CveReferenceOut,
    CveStats,
    PurgeOrphanedBody,
)
from cti_api.schemas.techstack import EXPOSURE_MULTIPLIER, HOSTING_MULTIPLIER

router = APIRouter(prefix="/api/cve", tags=["cve"])


def _serialize(
    cve: CveTracker,
    *,
    is_fp: bool,
    mentions: list[dict[str, str]],
    risk_ctx: dict[str, dict[str, str]],
) -> CveOut:
    ctx = risk_ctx.get((cve.tech or "").lower(), {})
    exposure = ctx.get("exposure", "internal")
    hosting = ctx.get("hosting_type", "on_prem")
    raw = cve.cve_score or 0.0
    exposure_mult = EXPOSURE_MULTIPLIER.get(exposure, 1.0)
    hosting_mult = HOSTING_MULTIPLIER.get(hosting, 1.0)
    adjusted = round(min(10.0, raw * exposure_mult * hosting_mult), 1) if raw else 0.0

    return CveOut(
        id=cve.id,
        cve_id=cve.cve_id,
        tech=cve.tech or "",
        link=cve.link or "",
        summary=cve.summary or "",
        published=cve.published.isoformat() if cve.published else "",
        reference=[CveReferenceOut(url=r.url) for r in cve.references],
        affected=[a.affected for a in cve.affected],
        solutions=cve.solutions or "",
        cve_score=raw,
        cve_severity=cve.cve_severity or "",
        cvss_vector=cve.cvss_vector or "",
        last_updated=cve.updated_at.isoformat() if cve.updated_at else "",
        poc_available=cve.poc_available,
        pocs=[
            CvePocOut(url=p.url, source=p.source or "", poc_type=p.poc_type or "poc")
            for p in cve.pocs
        ],
        false_positive=is_fp,
        detected_on=cve.detected_on.isoformat() if cve.detected_on else "",
        news_mentions_count=len(mentions),
        news_mentions=mentions,
        tech_exposure=exposure,
        hosting_type=hosting,
        adjusted_risk_score=adjusted,
    )


async def _active_tech_names(session: AsyncSession, client_id: str) -> list[str] | None:
    entries, _ = await AsyncTechStackRepo(session).list_filtered(
        client_id=client_id, page=1, page_size=10000
    )
    names = [e.name for e in entries]
    return names or None


@router.get("", response_model=CveListResponse)
async def list_cves(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    tech: list[str] | None = Query(None),
    severity: list[str] | None = Query(None),
    search: str | None = None,
    date_start: datetime.date | None = None,
    date_end: datetime.date | None = None,
    include_fp: bool = False,
    sort_by: str = Query("published", pattern="^(tech|severity|published|epss)$"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    session: AsyncSession = Depends(get_db),
    user: AuthedUser = Depends(require_auth),
    x_client_id: str | None = Header(None),
) -> CveListResponse:
    cid = effective_client_id(user, x_client_id)
    fp_repo = AsyncCveFalsePositiveRepo(session)
    fp_ids = await fp_repo.list_cve_ids(cid)
    fp_ids_set = set(fp_ids)

    effective_tech = tech or await _active_tech_names(session, cid)
    tracker_repo = AsyncCveTrackerRepo(session)
    cves, total = await tracker_repo.list_filtered(
        client_id=cid,
        page=page,
        page_size=page_size,
        tech=effective_tech,
        severity=severity,
        search=search,
        date_start=date_start,
        date_end=date_end,
        exclude_cve_ids=None if include_fp else fp_ids,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    tp_ids = [c.cve_id for c in cves if c.cve_id not in fp_ids_set]
    mentions_map = await tracker_repo.get_article_mentions(tp_ids)
    risk_ctx = await AsyncTechStackRepo(session).get_risk_context(cid)

    return CveListResponse(
        cves=[
            _serialize(
                c,
                is_fp=c.cve_id in fp_ids_set,
                mentions=mentions_map.get(c.cve_id, []),
                risk_ctx=risk_ctx,
            )
            for c in cves
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/stats", response_model=CveStats)
async def cve_stats(
    include_fp: bool = False,
    search: str | None = Query(None),
    severity: list[str] | None = Query(None),
    tech: list[str] | None = Query(None),
    date_start: datetime.date | None = Query(None),
    date_end: datetime.date | None = Query(None),
    session: AsyncSession = Depends(get_db),
    user: AuthedUser = Depends(require_auth),
    x_client_id: str | None = Header(None),
) -> CveStats:
    cid = effective_client_id(user, x_client_id)
    fp_ids = await AsyncCveFalsePositiveRepo(session).list_cve_ids(cid) if not include_fp else []
    effective_tech = tech or await _active_tech_names(session, cid)
    stats = await AsyncCveTrackerRepo(session).get_stats(
        client_id=cid,
        tech=effective_tech,
        severity=severity,
        search=search,
        date_start=date_start,
        date_end=date_end,
        exclude_cve_ids=fp_ids or None,
    )
    return CveStats(**stats)


@router.get("/tech-list")
async def tech_list(
    session: AsyncSession = Depends(get_db),
    user: AuthedUser = Depends(require_auth),
    x_client_id: str | None = Header(None),
) -> list[str]:
    cid = effective_client_id(user, x_client_id)
    return await AsyncCveTrackerRepo(session).get_tech_list(cid)


@router.post("/{cve_id}/false-positive")
async def set_false_positive(
    cve_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db),
    user: AuthedUser = Depends(require_auth),
    x_client_id: str | None = Header(None),
) -> dict[str, bool]:
    cid = effective_client_id(user, x_client_id)
    await AsyncCveFalsePositiveRepo(session).mark(cve_id, cid, marked_by=user["username"])
    await AsyncAuditLogRepo(session).write(
        username=user["username"],
        action="mark_false_positive",
        target_id=cve_id,
        ip_address=request_ip(request),
    )
    await session.commit()
    return {"ok": True}


@router.delete("/{cve_id}/false-positive")
async def remove_false_positive(
    cve_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db),
    user: AuthedUser = Depends(require_auth),
    x_client_id: str | None = Header(None),
) -> dict[str, bool]:
    cid = effective_client_id(user, x_client_id)
    await AsyncCveFalsePositiveRepo(session).unmark(cve_id, cid)
    await AsyncAuditLogRepo(session).write(
        username=user["username"],
        action="unmark_false_positive",
        target_id=cve_id,
        ip_address=request_ip(request),
    )
    await session.commit()
    return {"ok": True}


@router.post("/bulk-false-positive")
async def set_bulk_false_positive(
    body: BulkFalsePositiveBody,
    request: Request,
    session: AsyncSession = Depends(get_db),
    user: AuthedUser = Depends(require_auth),
    x_client_id: str | None = Header(None),
) -> dict[str, object]:
    cve_ids = body.cve_ids
    if not cve_ids:
        return {"ok": False, "detail": "cve_ids required"}
    if len(cve_ids) > 100:
        return {"ok": False, "detail": "max 100 CVEs per bulk operation"}
    cid = effective_client_id(user, x_client_id)
    marked = await AsyncCveFalsePositiveRepo(session).bulk_mark(
        cve_ids, cid, marked_by=user["username"]
    )
    await AsyncAuditLogRepo(session).write(
        username=user["username"],
        action="bulk_mark_false_positive",
        detail={"cve_ids": cve_ids, "count": marked},
        ip_address=request_ip(request),
    )
    await session.commit()
    return {"ok": True, "marked": marked}


@router.post("/purge-orphaned")
async def purge_orphaned(
    body: PurgeOrphanedBody,
    request: Request,
    session: AsyncSession = Depends(get_db),
    user: AuthedUser = Depends(require_auth),
    x_client_id: str | None = Header(None),
) -> dict[str, object]:
    """Hapus CVE yang tech-nya UDAH GAK ADA di techstack aktif client ini.
    `{"dry_run": false}` buat beneran eksekusi -- default preview doang."""
    dry_run = body.dry_run
    cid = effective_client_id(user, x_client_id)
    active_names = await _active_tech_names(session, cid) or []
    result = await AsyncCveTrackerRepo(session).purge_orphaned(
        client_id=cid, active_tech_names=active_names, dry_run=dry_run
    )
    if not dry_run:
        await AsyncAuditLogRepo(session).write(
            username=user["username"],
            action="purge_orphaned_cves",
            detail={"deleted": result.get("deleted", 0), "by_tech": result.get("by_tech")},
            ip_address=request_ip(request),
        )
    await session.commit()
    return result
