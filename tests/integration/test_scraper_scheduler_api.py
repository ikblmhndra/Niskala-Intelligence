"""Control plane: status scheduler (heartbeat beat) + `next_run_at` per scraper di
`GET /api/scraper` dan `GET /api/scraper/health` (QA BUG-D2/D8)."""

from __future__ import annotations

import datetime

from cti_core import beat_heartbeat
from cti_core.db.models.scraper import ScraperConfig
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


async def test_list_reports_unknown_scheduler_without_heartbeat(
    api_client: AsyncClient, auth_header
) -> None:
    resp = await api_client.get("/api/scraper", headers=auth_header(role="viewer"))
    assert resp.status_code == 200
    body = resp.json()

    assert body["scheduler"]["state"] == "unknown"
    assert body["scheduler"]["last_tick_at"] is None
    enabled = [s for s in body["scrapers"] if s["enabled"]]
    assert enabled and all(s["next_run_at"] for s in enabled)
    now = datetime.datetime.now(datetime.UTC)
    for s in enabled[:5]:
        assert datetime.datetime.fromisoformat(s["next_run_at"]) > now


async def test_list_reports_fresh_and_stale_heartbeat(
    api_client: AsyncClient, auth_header, fake_redis
) -> None:
    now = datetime.datetime.now(datetime.UTC)
    fake_redis.values[beat_heartbeat.HEARTBEAT_KEY] = beat_heartbeat.encode(
        now - datetime.timedelta(seconds=20), now - datetime.timedelta(hours=1)
    )
    body = (await api_client.get("/api/scraper", headers=auth_header())).json()
    assert body["scheduler"]["state"] == "ok"
    assert body["scheduler"]["started_at"] is not None

    fake_redis.values[beat_heartbeat.HEARTBEAT_KEY] = beat_heartbeat.encode(
        now - datetime.timedelta(hours=97), None
    )
    health = (await api_client.get("/api/scraper/health", headers=auth_header())).json()
    assert health["scheduler"]["state"] == "stale"
    assert health["scheduler"]["age_s"] > 96 * 3600


async def test_disabled_scraper_has_no_next_run(
    api_client: AsyncClient, api_session: AsyncSession, auth_header
) -> None:
    body = (await api_client.get("/api/scraper", headers=auth_header())).json()
    target = next(s for s in body["scrapers"] if s["enabled"])["id"]
    api_session.add(ScraperConfig(scraper_id=target, enabled=False))
    await api_session.flush()

    body = (await api_client.get("/api/scraper", headers=auth_header())).json()
    row = next(s for s in body["scrapers"] if s["id"] == target)
    assert row["enabled"] is False
    assert row["next_run_at"] is None
