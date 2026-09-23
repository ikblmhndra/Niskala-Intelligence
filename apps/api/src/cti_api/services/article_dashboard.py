"""Port `ScraperNewsWeb/app/services/article_service.py`'s
`get_dashboard_stats()`/`_fetch_dashboard_stats()`. Fase 7.4 Grup D --
endpoint `/api/dashboard` yang ketinggalan pas Fase 7.3 karena blocker
normalisasi negara (SEKARANG udah kejadian di enrichment, Fase 2/5,
lihat docstring `AsyncDashboardRepo` bagian "article dashboard").

Cache TTL module-level 900 detik (15 menit), pola sama kayak
`spike.py`/`risk_matrix.py`/`fp_analytics.py` -- per-proses uvicorn."""

from __future__ import annotations

import datetime
import time
from typing import Any

from cti_core.db.repositories.dashboard import AsyncDashboardRepo
from sqlalchemy.ext.asyncio import AsyncSession

_dashboard_cache: dict[str, tuple[dict[str, Any], float]] = {}
_CACHE_TTL = 900.0


async def get_dashboard_stats(
    session: AsyncSession,
    *,
    posted_on_start: datetime.date | None = None,
    posted_on_end: datetime.date | None = None,
) -> dict[str, Any]:
    start_key = posted_on_start.isoformat() if posted_on_start else ""
    end_key = posted_on_end.isoformat() if posted_on_end else ""
    cache_key = f"{start_key}|{end_key}"
    now = time.monotonic()
    cached = _dashboard_cache.get(cache_key)
    if cached is not None and (now - cached[1]) < _CACHE_TTL:
        return cached[0]

    result = await _fetch_dashboard_stats(
        session, posted_on_start=posted_on_start, posted_on_end=posted_on_end
    )
    _dashboard_cache[cache_key] = (result, now)
    return result


async def _fetch_dashboard_stats(
    session: AsyncSession,
    *,
    posted_on_start: datetime.date | None,
    posted_on_end: datetime.date | None,
) -> dict[str, Any]:
    repo = AsyncDashboardRepo(session)
    filters: dict[str, Any] = {
        "posted_on_start": posted_on_start,
        "posted_on_end": posted_on_end,
    }

    # Sekuensial (bukan `asyncio.gather`) -- satu `AsyncSession` gak aman
    # dipakai concurrent, constraint yang udah didokumentasikan berkali-
    # kali sesi ini (`exec_dashboard.py`, dst).
    total = await repo.count_articles(**filters)
    total_sources = await repo.distinct_source_count(**filters)
    total_countries = await repo.unique_mentioned_country_count(**filters)
    total_threat_actors = await repo.unique_threat_actor_count(**filters)
    top_countries = await repo.top_countries(limit=10, **filters)
    top_sources = await repo.top_sources(limit=10, **filters)
    top_actors = await repo.top_threat_actors(limit=10, **filters)
    top_industries = await repo.top_industries(limit=10, **filters)
    top_ttps = await repo.ttp_counts(limit=10, **filters)
    by_type = await repo.news_type_breakdown(**filters)
    timeline = await repo.article_timeline(**filters)

    return {
        "total_articles": total,
        "total_sources": total_sources,
        "total_countries": total_countries,
        "total_threat_actors": total_threat_actors,
        "top_countries": [{"name": c, "count": cnt} for c, cnt in top_countries],
        "top_sources": [{"name": s, "count": cnt} for s, cnt in top_sources],
        "top_threat_actors": [{"name": a, "count": cnt} for a, cnt in top_actors],
        "top_industries": [{"name": i, "count": cnt} for i, cnt in top_industries],
        "top_ttps": [{"name": f"{tid} — {tname}", "count": cnt} for tid, tname, cnt in top_ttps],
        "by_news_type": [{"name": nt, "count": cnt} for nt, cnt in by_type if nt],
        "timeline": [{"date": d.isoformat(), "count": cnt} for d, cnt in timeline],
    }
