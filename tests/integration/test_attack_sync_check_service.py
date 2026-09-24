"""Integration test `cti_api.services.attack_sync_check` -- Fase 7.8
(Celery beat "ATT&CK sync", salah satu dari 5 loop). Postgres REAL
(testcontainers). `AsyncAttackSyncRepo.sync_domain()` asli manggil
GitHub raw (STIX MITRE, ~30MB/domain) -- di-mock di sini, sama pola
kayak `test_attack_router_snapshot.py`."""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, patch

import pytest
from cti_api.services.attack_sync_check import sync_if_needed
from cti_core.db.models.attack import AttackSyncLog
from cti_core.db.repositories.attack import DOMAINS, AsyncAttackSyncRepo
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio


async def test_sync_runs_when_never_synced(async_db_session: AsyncSession) -> None:
    with patch.object(AsyncAttackSyncRepo, "sync_domain", AsyncMock(return_value={})):
        results = await sync_if_needed(async_db_session, interval_days=7)

    assert results is not None
    assert len(results) == len(DOMAINS)


async def test_sync_skipped_when_all_domains_fresh(async_db_session: AsyncSession) -> None:
    recent = (datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=1)).isoformat()
    async_db_session.add_all(
        [
            AttackSyncLog(
                domain_key=key,
                domain=key,
                label=meta["label"],
                status="success",
                last_sync=recent,
            )
            for key, meta in DOMAINS.items()
        ]
    )
    await async_db_session.flush()

    with patch.object(AsyncAttackSyncRepo, "sync_domain", AsyncMock(return_value={})) as mock_sync:
        results = await sync_if_needed(async_db_session, interval_days=7)

    assert results is None
    mock_sync.assert_not_called()


async def test_sync_runs_when_oldest_domain_past_interval(async_db_session: AsyncSession) -> None:
    fresh = (datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=1)).isoformat()
    stale = (datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=10)).isoformat()
    keys = list(DOMAINS)
    async_db_session.add_all(
        [
            AttackSyncLog(
                domain_key=key,
                domain=key,
                label=DOMAINS[key]["label"],
                status="success",
                last_sync=stale if key == keys[0] else fresh,
            )
            for key in keys
        ]
    )
    await async_db_session.flush()

    with patch.object(AsyncAttackSyncRepo, "sync_domain", AsyncMock(return_value={})):
        results = await sync_if_needed(async_db_session, interval_days=7)

    assert results is not None
    assert len(results) == len(DOMAINS)
