"""Integration test `cti_api.services.exec_dashboard`/`spike`/
`risk_matrix` -- Postgres REAL (testcontainers). Fase 7.3 (router
`exec_dashboard`/`intelligence`, Bagian 5)."""

from __future__ import annotations

import datetime

import pytest
from cti_api.services import exec_dashboard as exec_dashboard_service
from cti_api.services import risk_matrix as risk_matrix_service
from cti_api.services import spike as spike_service
from cti_core.db.models.cve import CveTracker
from cti_core.db.repositories.article import AsyncArticleRepo
from cti_core.db.repositories.auth import AsyncClientRepo
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio

_TODAY = datetime.date.today()


async def _ensure_clients(session: AsyncSession) -> None:
    await AsyncClientRepo(session).ensure_default()


async def _seed_incident_article(
    session: AsyncSession,
    *,
    url: str,
    industries: list[str],
    actors: list[str],
    posted_on: datetime.date,
) -> None:
    repo = AsyncArticleRepo(session)
    a = await repo.upsert(
        url=url,
        title=f"incident at {url}",
        source="BleepingComputer",
        posted_on=posted_on,
        news_type="Incident",
        confirmed_incident=True,
    )
    await repo.set_enrichment(a, industries=industries, threat_actors=actors)


async def test_get_exec_dashboard_v1_basic_shape(async_db_session: AsyncSession) -> None:
    await _ensure_clients(async_db_session)
    await _seed_incident_article(
        async_db_session,
        url="https://x.com/1",
        industries=["Manufacturing"],
        actors=["Apt41"],
        posted_on=_TODAY,
    )
    async_db_session.add(
        CveTracker(
            cve_id="CVE-2026-5555", client_id="default", tech="nginx", cve_severity="CRITICAL"
        )
    )
    await async_db_session.flush()

    result = await exec_dashboard_service.get_exec_dashboard(async_db_session, days=90)
    assert result["total_incidents"] == 1
    assert result["ta_leaderboard"] == [{"name": "Apt41", "count": 1}]
    assert result["top_sectors"] == ["Manufacturing"]
    wp = next(r for r in result["cve_exposure"] if r["tech"] == "nginx")
    assert wp["critical"] == 1


async def test_get_exec_dashboard_v2_includes_tier2_and_role_sections(
    async_db_session: AsyncSession,
) -> None:
    await _ensure_clients(async_db_session)
    await _seed_incident_article(
        async_db_session,
        url="https://x.com/2",
        industries=["Manufacturing"],
        actors=["Apt41"],
        posted_on=_TODAY,
    )
    async_db_session.add(
        CveTracker(
            cve_id="CVE-2026-6666", client_id="default", tech="nginx", cisa_kev=True, cve_score=9.8
        )
    )
    await async_db_session.flush()

    result = await exec_dashboard_service.get_exec_dashboard_v2(
        async_db_session, days=90, client_id="default", role="soc"
    )
    assert "sector_risk_scores" in result
    assert "ta_velocity" in result
    assert result["view_config"]["sections"]["critical_cve_feed"] is True
    assert any(c["cve_id"] == "CVE-2026-6666" for c in result["critical_cves"])
    # cluster_list deferred -- selalu kosong (lihat docstring service)
    assert result["recent_clusters_summary"] == []


async def test_build_view_config_role_gating() -> None:
    analyst = exec_dashboard_service.build_view_config("analyst")
    soc = exec_dashboard_service.build_view_config("soc")
    admin = exec_dashboard_service.build_view_config("admin")

    assert analyst["sections"]["fp_feedback_queue"] is True
    assert soc["sections"]["fp_feedback_queue"] is False
    assert admin["sections"]["fp_feedback_queue"] is True
    assert soc["sections"]["critical_cve_feed"] is True


async def test_get_spikes_detects_recent_surge(async_db_session: AsyncSession) -> None:
    await _ensure_clients(async_db_session)
    baseline_start = _TODAY - datetime.timedelta(days=20)
    for i in range(10):
        await _seed_incident_article(
            async_db_session,
            url=f"https://x.com/baseline/{i}",
            industries=["Manufacturing"],
            actors=["QuietActor"],
            posted_on=baseline_start + datetime.timedelta(days=i),
        )
    for i in range(8):
        await _seed_incident_article(
            async_db_session,
            url=f"https://x.com/surge/{i}",
            industries=["Manufacturing"],
            actors=["QuietActor"],
            posted_on=_TODAY,
        )

    result = await spike_service.get_spikes(async_db_session, lookback_days=30, z_threshold=1.5)
    actor_spikes = {s["entity"]: s for s in result["threat_actors"]}
    assert "QuietActor" in actor_spikes
    assert actor_spikes["QuietActor"]["count"] == 8


async def test_get_risk_matrix_scores_high_activity_cell(async_db_session: AsyncSession) -> None:
    await _ensure_clients(async_db_session)
    repo = AsyncArticleRepo(async_db_session)
    for i in range(4):
        a = await repo.upsert(
            url=f"https://x.com/matrix/{i}",
            title=f"matrix article {i}",
            source="s",
            posted_on=_TODAY,
        )
        await repo.set_enrichment(
            a,
            industries=["Manufacturing"],
            countries=[("US", "mentioned")],
            threat_actors=["Apt41", "Lazarus"],
            ttps=[("T1059", "Command Scripting")],
        )

    result = await risk_matrix_service.get_risk_matrix(async_db_session, days=30, compare_days=30)
    cell = next(
        r for r in result["matrix"] if r["industry"] == "Manufacturing" and r["country"] == "US"
    )
    assert cell["risk_score"] == 100
    assert set(cell["top_actors"]) == {"Apt41", "Lazarus"}
