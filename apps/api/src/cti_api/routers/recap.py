"""Port `ScraperNewsWeb/app/routers/recap.py`. SELURUH router ini
`require_auth`, port apa adanya (sama kayak kode lama -- gak ada
endpoint publik di sini)."""

from __future__ import annotations

import datetime

from cti_core.db.repositories.auth import AsyncAuditLogRepo
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from cti_api.deps import AuthedUser, get_db, request_ip, require_auth
from cti_api.services import recap as recap_service

router = APIRouter(prefix="/api/recap", tags=["recap"])


def _validate_date(date: str) -> None:
    try:
        datetime.datetime.strptime(date, "%Y-%m-%d")
    except ValueError as e:
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD") from e


@router.get("/list")
async def recap_list(
    limit: int = Query(30, ge=1, le=180),
    user: AuthedUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    return {"recaps": await recap_service.list_recaps(session, limit=limit)}


@router.get("/latest")
async def recap_latest(
    user: AuthedUser = Depends(require_auth), session: AsyncSession = Depends(get_db)
) -> dict[str, object]:
    yesterday = (datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=1)).strftime(
        "%Y-%m-%d"
    )
    doc = await recap_service.get_recap(session, yesterday)
    if not doc:
        return {"recap": None, "date": yesterday}
    return {"recap": doc, "date": yesterday}


@router.get("/{date}")
async def recap_get(
    date: str, user: AuthedUser = Depends(require_auth), session: AsyncSession = Depends(get_db)
) -> dict[str, object]:
    _validate_date(date)
    doc = await recap_service.get_recap(session, date)
    if not doc:
        raise HTTPException(status_code=404, detail=f"No recap for {date}")
    return {"recap": doc}


@router.post("/generate")
async def recap_generate(
    request: Request,
    date: str | None = Query(None, description="YYYY-MM-DD — defaults to yesterday"),
    force: bool = Query(False, description="Regenerate even if cached"),
    user: AuthedUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    if date:
        _validate_date(date)
    doc = await recap_service.generate_daily_recap(session, date=date, force=force)
    await AsyncAuditLogRepo(session).write(
        username=user["username"],
        action="generate_daily_recap",
        detail={"date": doc.get("date"), "force": force},
        ip_address=request_ip(request),
    )
    await session.commit()
    return {"recap": doc}
