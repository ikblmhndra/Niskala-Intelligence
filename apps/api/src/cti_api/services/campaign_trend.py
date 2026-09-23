"""Port `campaign_trend_service.py`. Fase 7.4 Grup A (2026-09-23) --
baca hasil PERSIST Pipeline 1 (`cti_api.services.cluster.get_clusters()`
-> tabel `clusters`), BUKAN Pipeline 2. Backing `GET /api/clusters/
evolution` + `GET /api/clusters/{id}/trends`."""

from __future__ import annotations

import datetime
from typing import Any

from cti_core.db.repositories.cluster import AsyncClusterRepo
from sqlalchemy.ext.asyncio import AsyncSession


def _slope(ys: list[float]) -> float:
    n = len(ys)
    if n < 2:
        return 0.0
    xs = list(range(n))
    x_mean = sum(xs) / n
    y_mean = sum(ys) / n
    num = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys, strict=True))
    den = sum((x - x_mean) ** 2 for x in xs)
    return num / den if den else 0.0


def _trend_direction(slope: float, recent_avg: float) -> str:
    if recent_avg < 0.5:
        return "dormant"
    if slope > 0.3:
        return "growing"
    if slope < -0.3:
        return "declining"
    return "stable"


async def get_campaign_trends(session: AsyncSession, cluster_id: str) -> dict[str, Any]:
    row = await AsyncClusterRepo(session).get_by_cluster_id(cluster_id)
    if row is None:
        return {}

    cutoff = (datetime.date.today() - datetime.timedelta(days=90)).isoformat()
    daily = [e for e in row.daily_counts if e.get("date", "") >= cutoff]
    daily.sort(key=lambda e: e["date"])

    timeline = [{"date": e["date"], "count": e["count"]} for e in daily]

    counts = [e["count"] for e in daily]
    last7 = counts[-7:] if len(counts) >= 7 else counts
    prior7 = counts[-14:-7] if len(counts) >= 14 else counts[: max(0, len(counts) - 7)]

    slope = _slope(last7)
    recent_avg = sum(last7) / len(last7) if last7 else 0.0
    trend_direction = _trend_direction(slope, recent_avg)

    last7_sum = sum(last7)
    prior7_sum = sum(prior7) if prior7 else 0
    if prior7_sum > 0:
        growth_rate = round((last7_sum - prior7_sum) / prior7_sum * 100, 1)
    elif last7_sum > 0:
        growth_rate = 100.0
    else:
        growth_rate = 0.0

    predicted_peak = None
    if slope > 0 and last7:
        current = last7[-1]
        peak_candidate = max(counts) if counts else current
        if current < peak_candidate * 1.5:
            days_to_peak = int((peak_candidate * 1.5 - current) / slope)
            if 0 < days_to_peak <= 30:
                predicted_peak = (
                    datetime.date.today() + datetime.timedelta(days=days_to_peak)
                ).isoformat()

    return {
        "cluster_id": cluster_id,
        "cluster_name": row.cluster_name,
        "trend_direction": trend_direction,
        "growth_rate": growth_rate,
        "predicted_peak": predicted_peak,
        "timeline": timeline,
        "slope": round(slope, 4),
        "recent_avg": round(recent_avg, 2),
    }


async def get_campaign_evolution(session: AsyncSession, *, days: int = 30) -> list[dict[str, Any]]:
    cutoff = datetime.date.today() - datetime.timedelta(days=days)
    rows = await AsyncClusterRepo(session).list_seen_since(cutoff)

    results = []
    for row in rows:
        trend = await get_campaign_trends(session, row.cluster_id)
        if trend:
            results.append(trend)

    results.sort(key=lambda x: x.get("growth_rate", 0), reverse=True)
    return results
