"""Integration test `cti_api.services.recap` -- Postgres REAL
(testcontainers), panggilan LLM di-mock (`unittest.mock.patch`, sama
pola kayak `tests/unit/test_mailer.py`) -- verifikasi LIVE terhadap LLM
gateway beneran dilakuin terpisah, bukan bagian suite otomatis ini.
Fase 7.3 (router `recap`, Bagian 5)."""

from __future__ import annotations

import datetime
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from cti_api.services import recap as recap_service
from cti_core.db.models.cve import CveTracker
from cti_core.db.repositories.article import AsyncArticleRepo
from cti_core.db.repositories.auth import AsyncClientRepo
from cti_core.db.repositories.ioc import AsyncIOCRepo
from cti_core.db.repositories.ta import AsyncTARepo
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio

_TODAY = datetime.date.today()


async def _ensure_clients(session: AsyncSession) -> None:
    await AsyncClientRepo(session).ensure_default()


async def test_collect_articles_sorted_by_reliability(async_db_session: AsyncSession) -> None:
    await _ensure_clients(async_db_session)
    repo = AsyncArticleRepo(async_db_session)
    await repo.upsert(
        url="https://x.com/a", title="from a tabloid", source="Vice", posted_on=_TODAY
    )
    await repo.upsert(url="https://x.com/b", title="from CISA", source="CISA", posted_on=_TODAY)

    articles = await recap_service._collect_articles(async_db_session, _TODAY)
    assert [a.source for a in articles] == ["CISA", "Vice"]


async def test_collect_iocs_and_cves_and_new_tas(async_db_session: AsyncSession) -> None:
    await _ensure_clients(async_db_session)
    await AsyncIOCRepo(async_db_session).upsert(
        type="ip", value="203.0.113.5", source_url="https://x.com/ioc", source_name="s"
    )
    async_db_session.add(
        CveTracker(cve_id="CVE-2026-7777", client_id="default", tech="nginx", registered_date=None)
    )
    await AsyncTARepo(async_db_session).add_group("Apt41")
    await async_db_session.flush()

    iocs = await recap_service._collect_iocs(async_db_session, _TODAY)
    assert len(iocs) == 1

    cves = await recap_service._collect_cves(async_db_session, _TODAY)
    assert any(c.cve_id == "CVE-2026-7777" for c in cves)

    new_tas = await recap_service._collect_new_threat_actors(async_db_session, _TODAY)
    assert any(t.name == "Apt41" for t in new_tas)


async def test_collect_campaigns_empty_db_returns_empty(async_db_session: AsyncSession) -> None:
    """Fase 7.4 Grup A -- `_collect_campaigns()` manggil pipeline
    beneran sekarang, bukan stub. DB kosong (< 2 artikel) -> `[]` lewat
    `get_recent_campaigns()`'s guard sendiri, bukan lagi stub statis."""
    assert await recap_service._collect_campaigns(async_db_session) == []


async def test_collect_campaigns_maps_fields_for_build_user_message(
    async_db_session: AsyncSession,
) -> None:
    """Regression buat bug legacy DITEMUKAN & DIPERBAIKI (lihat docstring
    modul) -- `_collect_campaigns()` HARUS ngirim key `theme`/
    `article_ids`/`threat_actors` (bukan `cluster_name`/
    `member_article_ids`/`dominant_tas` mentah dari `get_recent_
    campaigns()`), soalnya itu yang dibaca `_build_user_message()`."""
    await _ensure_clients(async_db_session)
    repo = AsyncArticleRepo(async_db_session)
    # `_collect_campaigns()` manggil `get_recent_campaigns(min_size=3)`
    # (hardcoded, port apa adanya) -- butuh MINIMAL 3 artikel se-cluster.
    titles = [
        "Apt41 hits target one today",
        "Apt41 hits target two today",
        "Apt41 hits target three today",
    ]
    for i, title in enumerate(titles):
        a = await repo.upsert(
            url=f"https://example.com/recap-campaign-{i}",
            title=title,
            source=f"S{i}",
            posted_on=_TODAY,
        )
        await repo.set_enrichment(a, threat_actors=["Apt41"])

    campaigns = await recap_service._collect_campaigns(async_db_session)
    assert len(campaigns) == 1
    assert campaigns[0]["theme"]
    assert campaigns[0]["size"] == 3
    assert campaigns[0]["threat_actors"] == ["Apt41"]
    assert len(campaigns[0]["article_ids"]) == 3

    # `_build_user_message()` HARUS nampilin nama campaign + actor,
    # BUKAN "(unlabeled) — 0 articles" (bug lama).
    msg = recap_service._build_user_message(
        _TODAY.isoformat(), [], [], [], [], campaigns, []
    )
    assert "(unlabeled) — 0 articles" not in msg
    assert "Apt41" in msg


def _fake_completion(content: str) -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


async def test_generate_daily_recap_caches_and_force_regenerates(
    async_db_session: AsyncSession,
) -> None:
    await _ensure_clients(async_db_session)
    fake_json = json.dumps(
        {
            "headline": "quiet day",
            "recap": {"summary": "nothing much happened"},
            "forecast": {"summary": "stay calm"},
        }
    )

    fake_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **kw: _fake_completion(fake_json))
        )
    )

    with patch.object(recap_service, "get_llm_client", return_value=(fake_client, "test-model")):
        date_iso = _TODAY.isoformat()
        first = await recap_service.generate_daily_recap(async_db_session, date=date_iso)
        assert first["headline"] == "quiet day"
        assert first["cached"] is False
        assert first["model"] == "test-model"

        second = await recap_service.generate_daily_recap(async_db_session, date=date_iso)
        assert second["cached"] is True
        assert second["id"] == first["id"]

        third = await recap_service.generate_daily_recap(
            async_db_session, date=date_iso, force=True
        )
        assert third["cached"] is False
        assert third["id"] == first["id"]


async def test_generate_daily_recap_handles_malformed_llm_json(
    async_db_session: AsyncSession,
) -> None:
    await _ensure_clients(async_db_session)
    fake_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=lambda **kw: _fake_completion("not valid json at all")
            )
        )
    )

    with patch.object(recap_service, "get_llm_client", return_value=(fake_client, "test-model")):
        result = await recap_service.generate_daily_recap(
            async_db_session, date="2026-08-01", force=True
        )
    assert result["headline"] == ""
    assert result["raw_llm"] == "not valid json at all"
