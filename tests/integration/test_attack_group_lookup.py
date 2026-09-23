"""Integration test `AsyncAttackQueryRepo.get_group_by_name_or_alias_ci`
-- Postgres REAL (testcontainers). Fase 7.4 Grup D (dibutuhin buat port
`iocs.py`'s `/ta-links/{type}/{value}`)."""

from __future__ import annotations

import pytest
from cti_core.db.models.attack import AttackGroup
from cti_core.db.repositories.attack import AsyncAttackQueryRepo
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio


async def _seed(session: AsyncSession) -> None:
    session.add(
        AttackGroup(
            stix_id="intrusion-set--abc123",
            group_id="G0096",
            name="APT41",
            aliases=["Wicked Panda", "Double Dragon", "BARIUM"],
            domains=["enterprise-attack"],
        )
    )
    await session.flush()


async def test_matches_by_exact_name_case_insensitive(async_db_session: AsyncSession) -> None:
    await _seed(async_db_session)
    repo = AsyncAttackQueryRepo(async_db_session)

    grp = await repo.get_group_by_name_or_alias_ci("apt41")
    assert grp is not None
    assert grp.group_id == "G0096"


async def test_matches_by_alias_case_insensitive(async_db_session: AsyncSession) -> None:
    await _seed(async_db_session)
    repo = AsyncAttackQueryRepo(async_db_session)

    grp = await repo.get_group_by_name_or_alias_ci("wicked panda")
    assert grp is not None
    assert grp.group_id == "G0096"


async def test_no_match_returns_none(async_db_session: AsyncSession) -> None:
    await _seed(async_db_session)
    repo = AsyncAttackQueryRepo(async_db_session)

    assert await repo.get_group_by_name_or_alias_ci("Nonexistent Actor") is None


async def test_empty_name_returns_none(async_db_session: AsyncSession) -> None:
    repo = AsyncAttackQueryRepo(async_db_session)
    assert await repo.get_group_by_name_or_alias_ci("") is None
    assert await repo.get_group_by_name_or_alias_ci("   ") is None


async def test_substring_does_not_match(async_db_session: AsyncSession) -> None:
    """Match HARUS persis (^...$ di legacy), bukan substring."""
    await _seed(async_db_session)
    repo = AsyncAttackQueryRepo(async_db_session)

    assert await repo.get_group_by_name_or_alias_ci("Panda") is None
    assert await repo.get_group_by_name_or_alias_ci("APT4") is None
