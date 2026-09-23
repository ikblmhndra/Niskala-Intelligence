"""Snapshot test `routers/techstack.py` -- Fase 7.6 (lanjutan pola
pilot `test_cve_router_snapshot.py`)."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from cti_core.db.repositories.techstack import AsyncTechStackRepo
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from syrupy.assertion import SnapshotAssertion
from syrupy.matchers import path_type

pytestmark = pytest.mark.asyncio

_NORMALIZE = path_type(
    {
        r"(.*\.)?id$": (int,),
        r"(.*\.)?added_date$": (str,),
    },
    regex=True,
    strict=False,
)


async def _seed_tech(session: AsyncSession) -> None:
    await AsyncTechStackRepo(session).create(
        name="WordPress", client_id="default", exposure="external", hosting_type="cloud"
    )


async def test_get_techstack(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
    snapshot: SnapshotAssertion,
) -> None:
    await _seed_tech(api_session)
    resp = await api_client.get("/api/techstack", headers=auth_header())
    assert resp.status_code == 200
    assert resp.json() == snapshot(matcher=_NORMALIZE)


async def test_post_techstack(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
    snapshot: SnapshotAssertion,
) -> None:
    resp = await api_client.post(
        "/api/techstack",
        headers=auth_header(),
        json={"name": "nginx", "exposure": "internal", "hosting_type": "on_prem"},
    )
    assert resp.status_code == 200
    assert resp.json() == snapshot(matcher=_NORMALIZE)


async def test_patch_exposure(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
    snapshot: SnapshotAssertion,
) -> None:
    await _seed_tech(api_session)
    items, _ = await AsyncTechStackRepo(api_session).list_filtered(client_id="default")
    resp = await api_client.patch(
        f"/api/techstack/{items[0].id}/exposure",
        headers=auth_header(),
        json={"exposure": "internal"},
    )
    assert resp.status_code == 200
    assert resp.json() == snapshot


async def test_patch_hosting(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
    snapshot: SnapshotAssertion,
) -> None:
    await _seed_tech(api_session)
    items, _ = await AsyncTechStackRepo(api_session).list_filtered(client_id="default")
    resp = await api_client.patch(
        f"/api/techstack/{items[0].id}/hosting",
        headers=auth_header(),
        json={"hosting_type": "on_prem"},
    )
    assert resp.status_code == 200
    assert resp.json() == snapshot


async def test_remove_techstack(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
    snapshot: SnapshotAssertion,
) -> None:
    await _seed_tech(api_session)
    items, _ = await AsyncTechStackRepo(api_session).list_filtered(client_id="default")
    resp = await api_client.delete(f"/api/techstack/{items[0].id}", headers=auth_header())
    assert resp.status_code == 200
    assert resp.json() == snapshot
