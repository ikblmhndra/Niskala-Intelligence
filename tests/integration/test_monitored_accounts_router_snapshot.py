"""Snapshot test `routers/monitored_accounts.py` -- Fase 7.6 (lanjutan
pola pilot `test_cve_router_snapshot.py`)."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from cti_core.db.repositories.tweet import AsyncMonitoredAccountRepo
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from syrupy.assertion import SnapshotAssertion
from syrupy.matchers import path_type

pytestmark = pytest.mark.asyncio

_NORMALIZE = path_type(
    {
        r"(.*\.)?id$": (int,),
        r"(.*\.)?added_at$": (str,),
    },
    regex=True,
    strict=False,
)


async def _seed_account(session: AsyncSession) -> None:
    await AsyncMonitoredAccountRepo(session).create(
        "threatintel", "Threat Intel Feed", "APAC focus"
    )


async def test_get_accounts(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
    snapshot: SnapshotAssertion,
) -> None:
    await _seed_account(api_session)
    resp = await api_client.get("/api/monitored-accounts", headers=auth_header())
    assert resp.status_code == 200
    assert resp.json() == snapshot(matcher=_NORMALIZE)


async def test_post_account(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
    snapshot: SnapshotAssertion,
) -> None:
    resp = await api_client.post(
        "/api/monitored-accounts",
        headers=auth_header(role="admin"),
        json={"username": "cti_source", "display_name": "CTI Source", "notes": "Verified feed"},
    )
    assert resp.status_code == 200
    assert resp.json() == snapshot(matcher=_NORMALIZE)


async def test_delete_account(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
    snapshot: SnapshotAssertion,
) -> None:
    await _seed_account(api_session)
    resp = await api_client.delete(
        "/api/monitored-accounts/threatintel", headers=auth_header(role="admin")
    )
    assert resp.status_code == 200
    assert resp.json() == snapshot


async def test_patch_toggle(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
    snapshot: SnapshotAssertion,
) -> None:
    await _seed_account(api_session)
    resp = await api_client.patch(
        "/api/monitored-accounts/threatintel/toggle",
        headers=auth_header(role="admin"),
        json={"active": False},
    )
    assert resp.status_code == 200
    assert resp.json() == snapshot
