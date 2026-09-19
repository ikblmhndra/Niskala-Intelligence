"""Port `ScraperNewsWeb/app/routers/intelligence.py`. **4 dari 7 endpoint
lama SENGAJA belum diport**: `GET /clusters`, `GET /clusters/recent`,
`GET /clusters/evolution`, `GET /clusters/{id}/trends`, `GET /intelligence/
geopolitical` (5 sebenarnya) -- SEMUA transitif butuh `cluster_service.py`
(784 baris TF-IDF/Jaccard clustering, di luar 27 router) lewat
`get_clusters()`/`get_recent_campaigns()`. `campaign_trend_service.py`
(`/clusters/{id}/trends`) & `geopolitical_service.py` (`/intelligence/
geopolitical`) juga transitif kena -- yang pertama baca `CLUSTERS_
COLLECTION` (output cluster_service), yang kedua nerima `campaigns` dari
`get_recent_campaigns()` sebagai parameter. Sama alasan persis kayak
`newsletter.include_clusters`/`mindmap`'s builder `cluster`/`exec_
dashboard`'s `recent_clusters_summary`.

3 endpoint yang PORTABLE (`spike_service.py`/`risk_matrix_service.py`/
`source_score_service.py` semuanya baca `articles` langsung, gak ada
dependency ke cluster) -- ini doang yang di-port."""

from __future__ import annotations

from cti_core.db.repositories.article import AsyncArticleRepo
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from cti_api.deps import get_db, require_auth
from cti_api.services import risk_matrix as risk_matrix_service
from cti_api.services import source_score as source_score_service
from cti_api.services import spike as spike_service

router = APIRouter(prefix="/api", tags=["intelligence"], dependencies=[Depends(require_auth)])


@router.get("/spikes")
async def early_warning(
    lookback_days: int = Query(30, ge=14, le=90),
    z_threshold: float = Query(2.0, ge=1.5, le=4.0),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    return await spike_service.get_spikes(
        session, lookback_days=lookback_days, z_threshold=z_threshold
    )


@router.get("/intelligence/risk-matrix")
async def risk_matrix(
    days: int = Query(30, ge=7, le=90),
    compare_days: int = Query(30, ge=7, le=90),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    return await risk_matrix_service.get_risk_matrix(session, days=days, compare_days=compare_days)


@router.get("/source-scores")
async def source_scores(session: AsyncSession = Depends(get_db)) -> dict[str, object]:
    options = await AsyncArticleRepo(session).get_filter_options()
    sources = sorted(s for s in options["sources"] if s)
    return {"sources": source_score_service.score_sources(sources)}
