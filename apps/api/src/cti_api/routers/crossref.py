"""Port dari `ScraperNewsWeb/app/routers/crossref.py`. SELURUH router
ini `require_auth` (deklarasi level-router), sama kayak `attack.py`/
`mitre.py`. `pir_id` sekarang `int` (path param), BUKAN `str` ObjectId --
FastAPI validasi tipe otomatis, gak butuh try/except `ObjectId(...)`
kayak kode lama."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from cti_api.deps import get_db, require_auth
from cti_api.services import crossref as crossref_service

router = APIRouter(prefix="/api/crossref", tags=["crossref"], dependencies=[Depends(require_auth)])


@router.get("/cve/{cve_id}")
async def cve_crossref(cve_id: str, session: AsyncSession = Depends(get_db)) -> dict[str, object]:
    result = await crossref_service.get_cve_crossrefs(session, cve_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/pir/{pir_id}")
async def pir_crossref(pir_id: int, session: AsyncSession = Depends(get_db)) -> dict[str, object]:
    result = await crossref_service.get_pir_crossrefs(session, pir_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/ta/{actor_name:path}")
async def ta_crossref(
    actor_name: str, session: AsyncSession = Depends(get_db)
) -> dict[str, object]:
    return await crossref_service.get_ta_crossrefs(session, actor_name)
