"""Snapshot test `routers/rfi.py` -- Fase 7.6 (lanjutan pola pilot
`test_cve_router_snapshot.py`)."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from cti_core.db.repositories.rfi import AsyncRFIRepo
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from syrupy.assertion import SnapshotAssertion
from syrupy.matchers import path_type

pytestmark = pytest.mark.asyncio

_NORMALIZE = path_type(
    {
        r"(.*\.)?id$": (int,),
        r"(.*\.)?created_at$": (str,),
        r"(.*\.)?updated_at$": (str,),
    },
    regex=True,
    strict=False,
)


async def _seed_rfi(session: AsyncSession) -> int:
    rfi = await AsyncRFIRepo(session).create(
        {"requester": "SOC Team", "question": "What is APT41's latest TTP?"}, client_id="default"
    )
    return rfi.id


async def test_get_rfis(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
    snapshot: SnapshotAssertion,
) -> None:
    await _seed_rfi(api_session)
    resp = await api_client.get("/api/rfi", headers=auth_header())
    assert resp.status_code == 200
    assert resp.json() == snapshot(matcher=_NORMALIZE)


async def test_get_rfi_by_id(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
    snapshot: SnapshotAssertion,
) -> None:
    rfi_id = await _seed_rfi(api_session)
    resp = await api_client.get(f"/api/rfi/{rfi_id}", headers=auth_header())
    assert resp.status_code == 200
    assert resp.json() == snapshot(matcher=_NORMALIZE)


async def test_post_rfi(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
    snapshot: SnapshotAssertion,
) -> None:
    resp = await api_client.post(
        "/api/rfi",
        headers=auth_header(),
        json={"requester": "Exec Team", "question": "Are we exposed to CVE-2026-0001?"},
    )
    assert resp.status_code == 200
    assert resp.json() == snapshot(matcher=_NORMALIZE)


async def test_put_rfi(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
    snapshot: SnapshotAssertion,
) -> None:
    rfi_id = await _seed_rfi(api_session)
    resp = await api_client.put(
        f"/api/rfi/{rfi_id}",
        headers=auth_header(),
        json={"status": "answered", "response": "No, unaffected."},
    )
    assert resp.status_code == 200
    assert resp.json() == snapshot(matcher=_NORMALIZE)


async def test_remove_rfi(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
    snapshot: SnapshotAssertion,
) -> None:
    rfi_id = await _seed_rfi(api_session)
    resp = await api_client.delete(f"/api/rfi/{rfi_id}", headers=auth_header())
    assert resp.status_code == 200
    assert resp.json() == snapshot
