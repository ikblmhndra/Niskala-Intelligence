"""Snapshot test `routers/crossref.py` -- Fase 7.6 (lanjutan pola pilot
`test_cve_router_snapshot.py`)."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from syrupy.assertion import SnapshotAssertion

pytestmark = pytest.mark.asyncio


async def test_cve_crossref_not_found(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
    snapshot: SnapshotAssertion,
) -> None:
    resp = await api_client.get("/api/crossref/cve/CVE-2099-9999", headers=auth_header())
    assert resp.status_code == 404
    assert resp.json() == snapshot


async def test_pir_crossref_not_found(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
    snapshot: SnapshotAssertion,
) -> None:
    resp = await api_client.get("/api/crossref/pir/999999", headers=auth_header())
    assert resp.status_code == 404
    assert resp.json() == snapshot


async def test_ta_crossref_empty(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
    snapshot: SnapshotAssertion,
) -> None:
    resp = await api_client.get("/api/crossref/ta/Apt41", headers=auth_header())
    assert resp.status_code == 200
    assert resp.json() == snapshot
