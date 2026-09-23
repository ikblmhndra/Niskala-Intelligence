"""Snapshot test `routers/ransomware.py` -- Fase 7.6 (lanjutan pola
pilot `test_cve_router_snapshot.py`)."""

from __future__ import annotations

import datetime
from collections.abc import Callable

import pytest
from cti_core.db.models.ransomware import RansomwareVictim
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from syrupy.assertion import SnapshotAssertion
from syrupy.matchers import path_type

pytestmark = pytest.mark.asyncio

_NORMALIZE = path_type({r"(.*\.)?id$": (int,)}, regex=True, strict=False)


async def _seed_victim(session: AsyncSession) -> None:
    session.add(
        RansomwareVictim(
            offset_key="LockBit:Acme Corp:US:2026-09-01",
            group_name="LockBit",
            victim="Acme Corp",
            country_code="US",
            industry="Manufacturing",
            published=datetime.date(2026, 9, 1),
            post_url="http://lockbit.example/post/1",
        )
    )
    await session.flush()


async def test_list_victims(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
    snapshot: SnapshotAssertion,
) -> None:
    await _seed_victim(api_session)
    resp = await api_client.get("/api/ransomware/victims", headers=auth_header())
    assert resp.status_code == 200
    assert resp.json() == snapshot(matcher=_NORMALIZE)


async def test_victim_filters(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
    snapshot: SnapshotAssertion,
) -> None:
    await _seed_victim(api_session)
    resp = await api_client.get("/api/ransomware/victims/filters", headers=auth_header())
    assert resp.status_code == 200
    assert resp.json() == snapshot


async def test_related_articles_empty(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
    snapshot: SnapshotAssertion,
) -> None:
    resp = await api_client.get("/api/ransomware/related-articles", headers=auth_header())
    assert resp.status_code == 200
    assert resp.json() == snapshot
