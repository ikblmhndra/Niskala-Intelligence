"""Port CRUD inti dari `ScraperNewsWeb/app/routers/techstack.py` -- lihat
docstring `cti_core.db.repositories.techstack` buat daftar lengkap yang
SENGAJA belum diport (backfill CVE lintas-client, trigger NVD/MITRE,
cascade-delete CVE) dan alasannya (nempel `cve.py`, belum ada di sini)."""

from __future__ import annotations

from cti_core.db.models.techstack import TechStackEntry
from cti_core.db.repositories.auth import AsyncAuditLogRepo
from cti_core.db.repositories.techstack import AsyncTechStackRepo
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from cti_api.deps import AuthedUser, effective_client_id, get_db, request_ip, require_auth
from cti_api.schemas.techstack import (
    TechStackAdd,
    TechStackExposureUpdate,
    TechStackHostingUpdate,
    TechStackListResponse,
    TechStackOut,
)

router = APIRouter(prefix="/api/techstack", tags=["techstack"])


def _serialize(entry: TechStackEntry) -> TechStackOut:
    return TechStackOut(
        id=entry.id,
        name=entry.name,
        added_date=entry.added_date.isoformat() if entry.added_date else "",
        source=entry.source or "",
        exposure=entry.exposure or "internal",
        hosting_type=entry.hosting_type or "on_prem",
    )


@router.get("", response_model=TechStackListResponse)
async def get_techstack(
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    sort_by: str = Query("name"),
    sort_dir: str = Query("asc"),
    session: AsyncSession = Depends(get_db),
    user: AuthedUser = Depends(require_auth),
    x_client_id: str | None = Header(None),
) -> TechStackListResponse:
    cid = effective_client_id(user, x_client_id)
    items, total = await AsyncTechStackRepo(session).list_filtered(
        client_id=cid,
        search=search,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return TechStackListResponse(
        items=[_serialize(i) for i in items], total=total, page=page, page_size=page_size
    )


@router.post("")
async def post_techstack(
    body: TechStackAdd,
    request: Request,
    session: AsyncSession = Depends(get_db),
    user: AuthedUser = Depends(require_auth),
    x_client_id: str | None = Header(None),
) -> dict[str, object]:
    cid = effective_client_id(user, x_client_id)
    entry, reason = await AsyncTechStackRepo(session).create(
        name=body.name, client_id=cid, exposure=body.exposure, hosting_type=body.hosting_type
    )
    if entry is None:
        return {"success": False, "reason": reason}
    await AsyncAuditLogRepo(session).write(
        username=user["username"],
        action="add_techstack",
        target_id=body.name,
        ip_address=request_ip(request),
    )
    await session.commit()
    return {"success": True, "item": _serialize(entry).model_dump()}


@router.patch("/{tech_id}/exposure")
async def patch_exposure(
    tech_id: int,
    body: TechStackExposureUpdate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    user: AuthedUser = Depends(require_auth),
    x_client_id: str | None = Header(None),
) -> dict[str, bool]:
    cid = effective_client_id(user, x_client_id)
    ok = await AsyncTechStackRepo(session).update_exposure(tech_id, body.exposure, cid)
    if not ok:
        raise HTTPException(status_code=404, detail="Tech not found or invalid exposure value")
    await AsyncAuditLogRepo(session).write(
        username=user["username"],
        action="update_techstack_exposure",
        target_id=str(tech_id),
        detail={"exposure": body.exposure},
        ip_address=request_ip(request),
    )
    await session.commit()
    return {"success": True}


@router.patch("/{tech_id}/hosting")
async def patch_hosting(
    tech_id: int,
    body: TechStackHostingUpdate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    user: AuthedUser = Depends(require_auth),
    x_client_id: str | None = Header(None),
) -> dict[str, bool]:
    cid = effective_client_id(user, x_client_id)
    ok = await AsyncTechStackRepo(session).update_hosting(tech_id, body.hosting_type, cid)
    if not ok:
        raise HTTPException(status_code=404, detail="Tech not found or invalid hosting type")
    await AsyncAuditLogRepo(session).write(
        username=user["username"],
        action="update_techstack_hosting",
        target_id=str(tech_id),
        detail={"hosting_type": body.hosting_type},
        ip_address=request_ip(request),
    )
    await session.commit()
    return {"success": True}


@router.delete("/{tech_id}")
async def remove_techstack(
    tech_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
    user: AuthedUser = Depends(require_auth),
    x_client_id: str | None = Header(None),
) -> dict[str, bool]:
    cid = effective_client_id(user, x_client_id)
    ok = await AsyncTechStackRepo(session).delete(tech_id, cid)
    await AsyncAuditLogRepo(session).write(
        username=user["username"],
        action="delete_techstack",
        target_id=str(tech_id),
        ip_address=request_ip(request),
    )
    await session.commit()
    return {"success": ok}
