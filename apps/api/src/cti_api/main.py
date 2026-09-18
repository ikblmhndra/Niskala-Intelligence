"""Entrypoint FastAPI -- port dari `ScraperNewsWeb/app/main.py`, TANPA
lima background loop (`_pir_alert_loop`, `_cve_enrichment_loop`, dst) dan
TANPA Jinja2/StaticFiles (frontend server-rendered lama diganti Next.js
terpisah, Fase 8 -- `apps/api` murni JSON API).

Lima loop itu bukan "belum sempat", tapi sengaja dipindah jadi item **7.8**
(lihat `docs/PROGRESS.md` Fase 6/7) -- ranahnya emang Celery beat
(`apps/worker`, Fase 6 udah nyediain infra-nya), bukan `asyncio.create_task`
di dalam proses uvicorn kayak dulu (itu masalahnya: >1 worker uvicorn
gandain semua loop N kali, salah satu alasan revamp)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from cti_core.config import get_settings
from cti_core.db.engine import async_session
from cti_core.db.repositories.auth import AsyncClientRepo
from cti_core.logging import configure_logging, get_logger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cti_api import __version__
from cti_api.routers import articles as articles_router
from cti_api.routers import auth as auth_router
from cti_api.routers import clients as clients_router
from cti_api.routers import health as health_router
from cti_api.routers import iocs as iocs_router
from cti_api.routers import roles as roles_router
from cti_api.services.roles import ensure_system_roles

log = get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(level=settings.log_level, json=settings.environment != "dev")
    async with async_session() as session:
        await AsyncClientRepo(session).ensure_default()
        await ensure_system_roles(session)
    log.info("api_startup_done", version=__version__)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="CTI Platform API", version=__version__, lifespan=lifespan)

    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Client-ID"],
    )

    app.include_router(health_router.router)
    app.include_router(auth_router.router)
    app.include_router(clients_router.router)
    app.include_router(roles_router.router)
    app.include_router(articles_router.router)
    app.include_router(iocs_router.router)
    return app


app = create_app()
