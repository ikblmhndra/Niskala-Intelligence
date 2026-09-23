"""Snapshot test `routers/mindmap.py` -- Fase 7.6 (lanjutan pola pilot
`test_cve_router_snapshot.py`). `feature_type="cve"` dipakai (registered
di `BUILDERS`, gak butuh data cluster/campaign yang lebih ribet buat
seed)."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from cti_core.db.models.cve import CveTracker
from cti_core.db.repositories.auth import AsyncClientRepo
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from syrupy.assertion import SnapshotAssertion
from syrupy.matchers import path_type

pytestmark = pytest.mark.asyncio

_NORMALIZE = path_type(
    {r"(.*\.)?generated_at$": (str,), r"(.*\.)?edited_at$": (str,)},
    regex=True,
    strict=False,
)


async def _seed_cve(session: AsyncSession) -> None:
    await AsyncClientRepo(session).ensure_default()
    session.add(
        CveTracker(
            cve_id="CVE-2026-9001",
            client_id="default",
            tech="WordPress",
            cve_score=9.8,
            cve_severity="CRITICAL",
        )
    )
    await session.flush()


async def test_get_mindmap_generates(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
    snapshot: SnapshotAssertion,
) -> None:
    await _seed_cve(api_session)
    resp = await api_client.get("/api/mindmap/cve/CVE-2026-9001", headers=auth_header())
    assert resp.status_code == 200
    assert resp.json() == snapshot(matcher=_NORMALIZE)


async def test_save_mindmap_edit(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
    snapshot: SnapshotAssertion,
) -> None:
    await _seed_cve(api_session)
    await api_client.get("/api/mindmap/cve/CVE-2026-9001", headers=auth_header())
    resp = await api_client.put(
        "/api/mindmap/cve/CVE-2026-9001",
        headers=auth_header(),
        json={"syntax": "mindmap\n  root((custom))"},
    )
    assert resp.status_code == 200
    assert resp.json() == snapshot(matcher=_NORMALIZE)


async def test_regenerate_mindmap(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
    snapshot: SnapshotAssertion,
) -> None:
    await _seed_cve(api_session)
    await api_client.get("/api/mindmap/cve/CVE-2026-9001", headers=auth_header())
    resp = await api_client.post("/api/mindmap/cve/CVE-2026-9001/regenerate", headers=auth_header())
    assert resp.status_code == 200
    assert resp.json() == snapshot(matcher=_NORMALIZE)
