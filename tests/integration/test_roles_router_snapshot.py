"""Snapshot test `routers/roles.py` -- Fase 7.6 (lanjutan pola pilot
`test_cve_router_snapshot.py`)."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from cti_api.services.roles import ensure_system_roles
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from syrupy.assertion import SnapshotAssertion
from syrupy.matchers import path_type

pytestmark = pytest.mark.asyncio

_NORMALIZE = path_type({r"(.*\.)?created_at$": (str,)}, regex=True, strict=False)


async def test_get_all_permissions(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
    snapshot: SnapshotAssertion,
) -> None:
    resp = await api_client.get("/api/roles/permissions", headers=auth_header())
    assert resp.status_code == 200
    assert resp.json() == snapshot


async def test_get_roles(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
    snapshot: SnapshotAssertion,
) -> None:
    await ensure_system_roles(api_session)
    resp = await api_client.get("/api/roles", headers=auth_header())
    assert resp.status_code == 200
    assert resp.json() == snapshot(matcher=_NORMALIZE)


async def test_add_role(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
    snapshot: SnapshotAssertion,
) -> None:
    resp = await api_client.post(
        "/api/roles",
        headers=auth_header(role="superadmin"),
        json={"name": "custom_role", "display_name": "Custom Role", "permissions": []},
    )
    assert resp.status_code == 200
    assert resp.json() == snapshot(matcher=_NORMALIZE)


async def test_remove_role(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
    snapshot: SnapshotAssertion,
) -> None:
    await api_client.post(
        "/api/roles",
        headers=auth_header(role="superadmin"),
        json={"name": "temp_role", "display_name": "Temp Role", "permissions": []},
    )
    resp = await api_client.delete("/api/roles/temp_role", headers=auth_header(role="superadmin"))
    assert resp.status_code == 200
    assert resp.json() == snapshot
