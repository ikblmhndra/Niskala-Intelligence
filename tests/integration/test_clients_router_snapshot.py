"""Snapshot test `routers/clients.py` -- Fase 7.6 (lanjutan pola pilot
`test_cve_router_snapshot.py`, TERAKHIR -- nutup 27/27 router)."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from cti_core.db.repositories.auth import AsyncClientRepo
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from syrupy.assertion import SnapshotAssertion
from syrupy.matchers import path_type

pytestmark = pytest.mark.asyncio

_NORMALIZE = path_type({r"(.*\.)?created_at$": (str,)}, regex=True, strict=False)


async def test_get_clients(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
    snapshot: SnapshotAssertion,
) -> None:
    resp = await api_client.get("/api/clients", headers=auth_header(role="admin"))
    assert resp.status_code == 200
    assert resp.json() == snapshot(matcher=_NORMALIZE)


async def test_post_client(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
    snapshot: SnapshotAssertion,
) -> None:
    resp = await api_client.post(
        "/api/clients",
        headers=auth_header(role="superadmin"),
        json={"client_id": "acme", "name": "Acme Corp", "countries": ["US"]},
    )
    assert resp.status_code == 201
    assert resp.json() == snapshot(matcher=_NORMALIZE)


async def test_edit_client(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
    snapshot: SnapshotAssertion,
) -> None:
    await AsyncClientRepo(api_session).create(client_id="acme", name="Acme Corp", countries=["US"])
    resp = await api_client.put(
        "/api/clients/acme",
        headers=auth_header(role="superadmin"),
        json={"name": "Acme Corporation", "countries": ["US", "CA"]},
    )
    assert resp.status_code == 200
    assert resp.json() == snapshot(matcher=_NORMALIZE)


async def test_remove_client(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
    snapshot: SnapshotAssertion,
) -> None:
    await AsyncClientRepo(api_session).create(client_id="acme", name="Acme Corp", countries=["US"])
    resp = await api_client.delete("/api/clients/acme", headers=auth_header(role="superadmin"))
    assert resp.status_code == 200
    assert resp.json() == snapshot


async def test_edit_client_omitted_countries_unchanged(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    """QA BUG-01 -- `countries` di-omit (atau `null`) = gak diubah, bukan
    diam-diam dikosongin."""
    await AsyncClientRepo(api_session).create(
        client_id="acme", name="Acme Corp", countries=["US", "CA"]
    )
    headers = auth_header(role="superadmin")
    for body in ({"name": "Acme Corporation"}, {"name": "Acme Corp II", "countries": None}):
        resp = await api_client.put("/api/clients/acme", headers=headers, json=body)
        assert resp.status_code == 200
        assert resp.json()["name"] == body["name"]
        assert sorted(resp.json()["countries"]) == ["CA", "US"]


async def test_edit_client_explicit_empty_countries_clears(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    await AsyncClientRepo(api_session).create(client_id="acme", name="Acme Corp", countries=["US"])
    resp = await api_client.put(
        "/api/clients/acme",
        headers=auth_header(role="superadmin"),
        json={"name": "Acme Corp", "countries": []},
    )
    assert resp.status_code == 200
    assert resp.json()["countries"] == []
