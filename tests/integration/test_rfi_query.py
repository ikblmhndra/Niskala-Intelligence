"""Integration test `AsyncRFIRepo` -- Postgres REAL (testcontainers).
Fase 7.3 (router `rfi`, Bagian 2)."""

from __future__ import annotations

import datetime

import pytest
from cti_core.db.repositories.auth import AsyncClientRepo
from cti_core.db.repositories.rfi import AsyncRFIRepo
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio


async def _ensure_clients(session: AsyncSession) -> None:
    repo = AsyncClientRepo(session)
    await repo.ensure_default()
    if await repo.get("acme") is None:
        await repo.create(client_id="acme", name="Acme", countries=[])


async def test_create_and_list(async_db_session: AsyncSession) -> None:
    await _ensure_clients(async_db_session)
    repo = AsyncRFIRepo(async_db_session)

    rfi = await repo.create(
        {"requester": "analyst1", "question": "Any IOC for APT41?"}, client_id="default"
    )
    assert rfi.status == "open"
    assert rfi.response == ""

    rfis, total = await repo.list_filtered(client_id="default")
    assert total == 1
    assert rfis[0].id == rfi.id


async def test_list_filtered_by_status(async_db_session: AsyncSession) -> None:
    await _ensure_clients(async_db_session)
    repo = AsyncRFIRepo(async_db_session)
    await repo.create({"requester": "a1", "question": "q1", "status": "open"}, client_id="default")
    await repo.create(
        {"requester": "a2", "question": "q2", "status": "closed"}, client_id="default"
    )

    open_rfis, total_open = await repo.list_filtered(client_id="default", status="open")
    assert total_open == 1
    assert open_rfis[0].status == "open"


async def test_list_filtered_scoped_by_client(async_db_session: AsyncSession) -> None:
    await _ensure_clients(async_db_session)
    repo = AsyncRFIRepo(async_db_session)
    await repo.create({"requester": "a1", "question": "q1"}, client_id="default")
    await repo.create({"requester": "a2", "question": "q2"}, client_id="acme")

    _, total_default = await repo.list_filtered(client_id="default")
    _, total_acme = await repo.list_filtered(client_id="acme")
    assert total_default == 1
    assert total_acme == 1


async def test_get_by_id_scoped_by_client_returns_none_for_wrong_client(
    async_db_session: AsyncSession,
) -> None:
    await _ensure_clients(async_db_session)
    repo = AsyncRFIRepo(async_db_session)
    rfi = await repo.create({"requester": "a1", "question": "q1"}, client_id="default")

    assert await repo.get_by_id(rfi.id, "default") is not None
    assert await repo.get_by_id(rfi.id, "acme") is None


async def test_update_ignores_client_scope(async_db_session: AsyncSession) -> None:
    """Port apa adanya: `update_rfi` lama gak nge-filter client_id sama
    sekali -- beda dari `list`/`get`/`create` di file yang sama. Lihat
    docstring modul `cti_core.db.repositories.rfi`."""
    await _ensure_clients(async_db_session)
    repo = AsyncRFIRepo(async_db_session)
    rfi = await repo.create({"requester": "a1", "question": "q1"}, client_id="default")

    updated = await repo.update(rfi.id, {"status": "in_progress", "response": "checking"})
    assert updated is not None
    assert updated.status == "in_progress"
    assert updated.response == "checking"


async def test_update_missing_returns_none(async_db_session: AsyncSession) -> None:
    repo = AsyncRFIRepo(async_db_session)
    assert await repo.update(999999, {"status": "closed"}) is None


async def test_delete_ignores_client_scope(async_db_session: AsyncSession) -> None:
    await _ensure_clients(async_db_session)
    repo = AsyncRFIRepo(async_db_session)
    rfi = await repo.create({"requester": "a1", "question": "q1"}, client_id="default")

    assert await repo.delete(rfi.id) is True
    assert await repo.get_by_id_unscoped(rfi.id) is None


async def test_delete_missing_returns_false(async_db_session: AsyncSession) -> None:
    repo = AsyncRFIRepo(async_db_session)
    assert await repo.delete(999999) is False


async def test_linked_pir_fk_set_null_on_pir_delete(async_db_session: AsyncSession) -> None:
    """`linked_pir_id` FK asli (`ondelete=SET NULL`) -- beda dari kode
    lama yang cuma nyimpen string ObjectId lepas tanpa validasi apa pun."""
    from cti_core.db.repositories.pir import AsyncPIRRepo

    await _ensure_clients(async_db_session)
    pir_repo = AsyncPIRRepo(async_db_session)
    pir = await pir_repo.create({"title": "Track APT41"}, client_id="default")

    rfi_repo = AsyncRFIRepo(async_db_session)
    rfi = await rfi_repo.create(
        {"requester": "a1", "question": "q1", "linked_pir": pir.id}, client_id="default"
    )
    assert rfi.linked_pir_id == pir.id

    await pir_repo.delete(pir.id)
    await async_db_session.refresh(rfi)
    assert rfi.linked_pir_id is None


async def test_create_with_due_date(async_db_session: AsyncSession) -> None:
    await _ensure_clients(async_db_session)
    repo = AsyncRFIRepo(async_db_session)
    rfi = await repo.create(
        {"requester": "a1", "question": "q1", "due_date": datetime.date(2026, 10, 1)},
        client_id="default",
    )
    assert rfi.due_date == datetime.date(2026, 10, 1)
