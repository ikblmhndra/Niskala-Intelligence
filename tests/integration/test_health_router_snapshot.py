"""Snapshot test `routers/health.py` -- Fase 7.6 (lanjutan pola pilot
`test_cve_router_snapshot.py`). `version` (`cti_api.__version__`) ikutan
snapshot -- kalau berubah pas rilis, snapshot di-update via
`--snapshot-update`, bukan tanda regresi."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from syrupy.assertion import SnapshotAssertion

pytestmark = pytest.mark.asyncio


async def test_healthz(
    api_client: AsyncClient, api_session: AsyncSession, snapshot: SnapshotAssertion
) -> None:
    resp = await api_client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == snapshot
