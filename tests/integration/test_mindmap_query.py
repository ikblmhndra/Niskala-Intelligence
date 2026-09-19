"""Integration test `AsyncMindmapRepo` + builder `cti_api.services.mindmap`
-- Postgres REAL (testcontainers). Fase 7.3 (router `mindmap`, Bagian 4)."""

from __future__ import annotations

import datetime

import pytest
from cti_api.services import mindmap as mindmap_service
from cti_core.db.models.cve import CveAffected, CvePoc, CveTracker
from cti_core.db.models.ransomware import RansomwareVictim
from cti_core.db.repositories.article import AsyncArticleRepo
from cti_core.db.repositories.auth import AsyncClientRepo
from cti_core.db.repositories.mindmap import AsyncMindmapRepo, get_display_syntax
from cti_core.db.repositories.newsletter import AsyncNewsletterRepo
from cti_core.db.repositories.pir import AsyncPIRRepo
from cti_core.db.repositories.ta import AsyncTAProfileRepo, AsyncTARepo
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio


async def _ensure_clients(session: AsyncSession) -> None:
    await AsyncClientRepo(session).ensure_default()


# ── AsyncMindmapRepo cache CRUD ──────────────────────────────────────────────


async def test_save_and_get_cached(async_db_session: AsyncSession) -> None:
    repo = AsyncMindmapRepo(async_db_session)
    doc = await repo.save("cve", "CVE-2026-0001", "CVE-2026-0001", "mindmap\n  root((x))\n")
    assert doc.mermaid_syntax.startswith("mindmap")

    cached = await repo.get_cached("cve", "CVE-2026-0001")
    assert cached is not None
    assert cached.id == doc.id


async def test_save_overwrites_existing_and_clears_custom_syntax(
    async_db_session: AsyncSession,
) -> None:
    repo = AsyncMindmapRepo(async_db_session)
    await repo.save("cve", "CVE-2026-0001", "t1", "syntax1")
    await repo.save_custom_syntax("cve", "CVE-2026-0001", "edited by analyst")

    updated = await repo.save("cve", "CVE-2026-0001", "t2", "syntax2")
    assert updated.mermaid_syntax == "syntax2"
    assert updated.custom_syntax is None
    assert updated.edited_at is None


async def test_save_custom_syntax_missing_doc_returns_none(async_db_session: AsyncSession) -> None:
    repo = AsyncMindmapRepo(async_db_session)
    assert await repo.save_custom_syntax("cve", "CVE-9999-9999", "x") is None


async def test_get_display_syntax_prefers_custom(async_db_session: AsyncSession) -> None:
    repo = AsyncMindmapRepo(async_db_session)
    doc = await repo.save("cve", "CVE-2026-0001", "t", "generated-syntax")
    assert get_display_syntax(doc) == "generated-syntax"

    edited = await repo.save_custom_syntax("cve", "CVE-2026-0001", "custom-syntax")
    assert edited is not None
    assert get_display_syntax(edited) == "custom-syntax"


# ── Builders ─────────────────────────────────────────────────────────────────


async def test_build_cve_mindmap(async_db_session: AsyncSession) -> None:
    cve = CveTracker(
        cve_id="CVE-2026-0001",
        client_id="default",
        tech="WordPress",
        cve_severity="CRITICAL",
        cve_score=9.8,
        cisa_kev=True,
        poc_available=True,
        summary="Actor exploits via T1059 scripting.",
        published=datetime.date(2026, 9, 1),
    )
    cve.affected = [CveAffected(affected="wordpress <= 6.5")]
    cve.pocs = [CvePoc(url="https://github.com/poc/exploit")]
    await _ensure_clients(async_db_session)
    async_db_session.add(cve)
    await async_db_session.flush()

    result = await mindmap_service.build_cve_mindmap(async_db_session, "CVE-2026-0001")
    assert result is not None
    title, syntax = result
    assert title == "CVE-2026-0001"
    assert "mindmap" in syntax
    assert "T1059" in syntax
    assert "CISA KEV" in syntax


async def test_build_cve_mindmap_missing_returns_none(async_db_session: AsyncSession) -> None:
    result = await mindmap_service.build_cve_mindmap(async_db_session, "CVE-9999-9999")
    assert result is None


async def test_build_threat_actor_mindmap_requires_tracked_group(
    async_db_session: AsyncSession,
) -> None:
    # Profil ADA tapi grup gak di-track -- port apa adanya, mindmap TA
    # cuma jalan buat nama yang ada di `threat_actor_groups`.
    await AsyncTAProfileRepo(async_db_session).save_profile(
        "Apt41", {"identity": {"actor_type": "x"}}
    )
    result = await mindmap_service.build_threat_actor_mindmap(async_db_session, "Apt41")
    assert result is None

    await AsyncTARepo(async_db_session).add_group("Apt41")
    result2 = await mindmap_service.build_threat_actor_mindmap(async_db_session, "apt41")
    assert result2 is not None
    title, syntax = result2
    assert "Apt41" in title
    assert "mindmap" in syntax


async def test_build_pir_mindmap(async_db_session: AsyncSession) -> None:
    await _ensure_clients(async_db_session)
    article_repo = AsyncArticleRepo(async_db_session)
    a1 = await article_repo.upsert(
        url="https://example.com/apt41", title="APT41 T1059 campaign", source="s"
    )
    # `industries` juga ada di criteria PIR di bawah -- match-nya AND
    # (lihat `_apply_list_filters`), jadi artikel seed HARUS ditag industri
    # yang sama juga, bukan cuma threat_actors.
    await article_repo.set_enrichment(a1, threat_actors=["Apt41"], industries=["Gov"])

    pir = await AsyncPIRRepo(async_db_session).create(
        {"title": "Track APT41", "criteria": {"threat_actors": ["Apt41"], "industries": ["Gov"]}},
        client_id="default",
    )

    result = await mindmap_service.build_pir_mindmap(async_db_session, str(pir.id))
    assert result is not None
    title, syntax = result
    assert title == "Track APT41"
    assert "Apt41" in syntax
    assert "T1059" in syntax


async def test_build_pir_mindmap_missing_returns_none(async_db_session: AsyncSession) -> None:
    result = await mindmap_service.build_pir_mindmap(async_db_session, "999999")
    assert result is None


async def test_build_ransomware_mindmap(async_db_session: AsyncSession) -> None:
    async_db_session.add_all(
        [
            RansomwareVictim(
                offset_key="k1",
                group_name="LockBit",
                victim="Acme Corp",
                country_code="US",
                industry="Manufacturing",
                published=datetime.date(2026, 9, 1),
            ),
            RansomwareVictim(
                offset_key="k2",
                group_name="LockBit",
                victim="Widget Inc",
                country_code="US",
                industry="Manufacturing",
                published=datetime.date(2026, 9, 2),
            ),
        ]
    )
    await async_db_session.flush()

    # `group_name` yang dibalikin di title APA ADANYA input caller (bukan
    # casing kanonik dari DB) -- port persis `f"Ransomware: {group_name}"`
    # lama, exact-match query-nya sendiri tetap case-insensitive.
    result = await mindmap_service.build_ransomware_mindmap(async_db_session, "lockbit")
    assert result is not None
    title, syntax = result
    assert title == "Ransomware: lockbit"
    assert "Acme Corp" in syntax
    # `_esc()` strip tanda kurung (buat aman disisipin ke syntax Mermaid) --
    # "Manufacturing (2)" jadi "Manufacturing 2", port apa adanya.
    assert "Manufacturing 2" in syntax


async def test_build_newsletter_mindmap(async_db_session: AsyncSession) -> None:
    row = await AsyncNewsletterRepo(async_db_session).save(
        week=38,
        year=2026,
        generated_at="x",
        created_by="a",
        html="<html/>",
        sections={
            "highlight": {"title": "Big breach happens"},
            "apac": [{"title": "APAC article"}],
            "global_news": [],
            "indonesia": [],
        },
    )

    result = await mindmap_service.build_newsletter_mindmap(async_db_session, str(row.id))
    assert result is not None
    title, syntax = result
    assert title == "Newsletter Week 38/2026"
    assert "Big breach happens" in syntax
    assert "APAC article" in syntax


async def test_build_newsletter_mindmap_missing_returns_none(
    async_db_session: AsyncSession,
) -> None:
    result = await mindmap_service.build_newsletter_mindmap(async_db_session, "999999")
    assert result is None


# ── get_or_generate orchestration ────────────────────────────────────────────


async def test_get_or_generate_caches_after_first_call(async_db_session: AsyncSession) -> None:
    cve = CveTracker(cve_id="CVE-2026-0001", client_id="default", tech="WordPress")
    await _ensure_clients(async_db_session)
    async_db_session.add(cve)
    await async_db_session.flush()

    doc1 = await mindmap_service.get_or_generate(async_db_session, "cve", "CVE-2026-0001")
    assert doc1 is not None

    # Ganti data CVE-nya -- kalau get_or_generate BENERAN kepake cache,
    # syntax gak bakal ikut berubah tanpa /regenerate eksplisit.
    cve.tech = "nginx"
    await async_db_session.flush()

    doc2 = await mindmap_service.get_or_generate(async_db_session, "cve", "CVE-2026-0001")
    assert doc2 is not None
    assert doc2.id == doc1.id
    assert doc2.mermaid_syntax == doc1.mermaid_syntax


async def test_get_or_generate_unknown_doc_returns_none(async_db_session: AsyncSession) -> None:
    result = await mindmap_service.get_or_generate(async_db_session, "cve", "CVE-9999-9999")
    assert result is None
