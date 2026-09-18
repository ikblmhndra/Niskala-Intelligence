"""Health check dasar -- BUKAN control plane scraper (itu Fase 9,
`/api/scraper/health`). Ini cuma "proses API-nya hidup dan bisa jawab"."""

from __future__ import annotations

from fastapi import APIRouter

from cti_api import __version__

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "version": __version__}
