"""Snapshot test `routers/changelog.py` -- Fase 7.6 (lanjutan pola pilot
`test_cve_router_snapshot.py`).

Endpoint ini baca `CHANGELOG.md` ASLI dari disk, bukan data seed
terkontrol -- isinya SENGAJA berubah tiap rilis (entry baru nambah).
Snapshot literal gak cocok di sini (bakal basi tiap `CHANGELOG.md`
diedit, padahal itu perubahan yang DIHARAPKAN, bukan regresi) -- jadi
dites lewat assert struktur langsung (shape: list of dict dengan key
yang bener), bukan `snapshot`."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio


async def test_list_versions_unauthenticated(
    api_client: AsyncClient, api_session: AsyncSession
) -> None:
    resp = await api_client.get("/api/changelog")
    assert resp.status_code == 401  # require_auth level-router, no token


async def test_list_versions(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    resp = await api_client.get("/api/changelog", headers=auth_header())
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) >= 1
    assert all({"version", "date"} <= set(item.keys()) for item in body)
    assert any(item["version"] == "0.1.0" for item in body)


async def test_get_version_found(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    resp = await api_client.get("/api/changelog/0.1.0", headers=auth_header())
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] == "0.1.0"
    assert {"version", "date", "content"} <= set(body.keys())


async def test_get_version_not_found(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    resp = await api_client.get("/api/changelog/99.99.99", headers=auth_header())
    assert resp.status_code == 404
