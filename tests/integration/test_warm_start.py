"""`tools/seed/fase10_warm_start.py` -- isi `scraper_seen` dari dump lama (10.C).

Dua hal yang dikunci:

  1. Perencanaan: dari bentuk dump lama (`offsets`/`nlp_jobs`/`articles`) ke
     kunci dedup yang BENAR-BENAR dihitung `Runner`. Bentuk key lama yang licin
     (title+url tanpa pemisah, CISA = judul+tanggal, Splunk = judul+path relatif)
     sengaja dimasukkan -- itu yang ada di dump asli.
  2. Efeknya: scraper yang di-warm-start GAK kena cold-start cap dan cuma
     meloloskan item yang benar-benar baru. Ini test yang penting -- kalau hash
     di script beda sedikit saja dengan hash runner, semua test perencanaan
     tetap hijau tapi warm start diam-diam gak ngapa-ngapain.
"""

from __future__ import annotations

import datetime
import pathlib
from collections.abc import Callable, Iterator

import pytest
from cti_core.db.models.scraper import ScraperSeen
from cti_core.urlkit import canonicalize_url
from cti_scraper.base import BaseScraper, ScrapeContext, ScraperMeta
from cti_scraper.dedup import compute_dedup_key
from cti_scraper.items import ArticleItem, Item
from cti_scraper.runner import Runner
from sqlalchemy import select
from sqlalchemy.orm import Session

from tools.seed import fase10_warm_start as ws
from tools.seed._dump import DirDump, MemoryDump

SID = "test-warm"
NOW = datetime.datetime(2026, 9, 26, 12, 0, tzinfo=datetime.UTC)


def index(**over: object) -> ws.Index:
    base = {
        "by_script": {"fooThreat": SID, "gonThreat": "test-gone-not-here"},
        "by_label": {"NEW ARTICLE FROM FOO": SID},
        "by_source": {"foo": SID, "old label": SID, "retired": None},
        "article_scrapers": {SID},
        "ttl_days": {SID: 30, "ransomware_live": 400, "monitor_x": 180},
    }
    return ws.Index(**{**base, **over})  # type: ignore[arg-type]


def key(url: str) -> str:
    return compute_dedup_key(SID, canonicalize_url(url))


def plan_for(**collections: list[dict]) -> ws.Plan:
    dump = MemoryDump({name.replace("__", "/"): docs for name, docs in collections.items()})
    return ws.build_plan(dump, index())


A = "https://foo.example/blog/a?utm_source=x"
B = "https://foo.example/blog/b"


# --- perencanaan ----------------------------------------------------------------------


def test_offsets_key_is_resolved_to_the_url_via_known_title_url_pairs() -> None:
    # `key` lama = str(title)+str(url), tanpa pemisah.
    plan = plan_for(
        threatintel__nlp_jobs=[
            {"script_name": "NEW ARTICLE FROM FOO", "article": {"title": "Judul A", "url": A}}
        ],
        threatintel__offsets=[
            {"script": "fooThreat", "key": "Judul A" + A, "seen_at": datetime.datetime(2026, 5, 1)}
        ],
    )

    assert set(plan.seen[SID]) == {key(A)}  # satu kunci, bukan dua: nlp_jobs & offsets nyambung
    entry = plan.seen[SID][key(A)]
    assert entry.sources == {"nlp_jobs", "offsets"}
    assert entry.seen_at == datetime.datetime(2026, 5, 1)  # tercatat paling awal
    assert not plan.unresolved


def test_key_shapes_that_are_not_a_plain_url_are_resolved_by_title_prefix() -> None:
    cisa_url = "https://nvd.nist.gov/vuln/detail/CVE-2026-1 || https://vendor.example/adv"
    splunk_url = "https://www.splunk.com/en_us/blog/security/top-50.html"
    plan = plan_for(
        threatintel__nlp_jobs=[
            {"script_name": "NEW ARTICLE FROM FOO",
             "article": {"title": "CVE-2026-1", "url": cisa_url}},
            {"script_name": "NEW ARTICLE FROM FOO",
             "article": {"title": "Top 50 Threats", "url": splunk_url}},
        ],
        threatintel__offsets=[
            {"script": "fooThreat", "key": "CVE-2026-12026-04-28"},  # judul + tanggal
            {"script": "fooThreat", "key": "Top 50 Threats/en_us/blog/security/top-50.html"},
        ],
    )  # fmt: skip

    assert set(plan.seen[SID]) == {key(cisa_url), key(splunk_url)}
    assert not plan.unresolved


def test_offsets_key_with_a_bare_url_tail_needs_no_known_pair() -> None:
    plan = plan_for(threatintel__offsets=[{"script": "fooThreat", "key": "Judul tak dikenal" + B}])

    assert set(plan.seen[SID]) == {key(B)}


def test_key_with_no_recoverable_url_is_reported_not_guessed() -> None:
    plan = plan_for(threatintel__offsets=[{"script": "fooThreat", "key": "cuma teks tanpa url"}])

    assert not plan.seen
    assert plan.unresolved[SID] == 1
    assert plan.unresolved_samples[SID] == ["cuma teks tanpa url"]


def test_articles_are_matched_by_source_label_and_alias() -> None:
    plan = plan_for(
        news_db__articles=[
            {"source": "Foo", "title": "t", "url": A},
            {"source": "Old Label", "title": "t2", "url": B},  # alias
            {
                "source": "Retired",
                "title": "t3",
                "url": "https://x.example/3",
            },  # sengaja gak diport
            {"source": "Ghost", "title": "t4", "url": "https://x.example/4"},
        ]
    )

    assert set(plan.seen[SID]) == {key(A), key(B)}
    assert plan.dropped == {"articles:Retired": 1, "articles:Ghost": 1}


def test_label_variants_with_a_parenthetical_suffix_map_to_the_same_scraper() -> None:
    plan = plan_for(
        threatintel__nlp_jobs=[
            {"script_name": "NEW ARTICLE FROM FOO (RELATED)", "article": {"title": "t", "url": A}}
        ]
    )

    assert set(plan.seen[SID]) == {key(A)}
    assert not plan.dropped


def test_scripts_without_a_scraper_are_counted_as_dropped() -> None:
    plan = plan_for(
        threatintel__offsets=[{"script": "retiredThreat", "key": "x" + A}],
        threatintel__nlp_jobs=[{"script_name": "NEW ARTICLE FROM RETIRED", "article": {}}],
    )

    assert not plan.seen
    assert plan.dropped == {"offsets:retiredThreat": 1, "nlp_jobs:NEW ARTICLE FROM RETIRED": 1}


def test_non_article_scrapers_are_never_seeded_from_url_sources() -> None:
    """CveItem/TweetItem/... punya format kunci sendiri -- nebak dari URL bikin
    hash yang gak pernah cocok dan gak pernah ketahuan."""
    idx = index(article_scrapers=set())  # SID BUKAN scraper artikel
    dump = MemoryDump(
        {
            "threatintel/offsets": [{"script": "fooThreat", "key": "x" + A}],
            "news_db/articles": [{"source": "Foo", "title": "t", "url": A}],
        }
    )

    assert not ws.build_plan(dump, idx).seen


def test_ransomware_and_tweets_use_their_own_native_keys() -> None:
    victim_key = "incransom:nbd3pl.com:US:Transportation/Logistics:2026-04-29"
    plan = plan_for(
        news_db__ransomware_victims=[{"offset_key": victim_key}, {"group_name": "tanpa key"}],
        news_db__tweets=[{"tweet_id": "2054094495562559812"}],
    )

    # kunci mentah PERSIS apa adanya -- BUKAN canonicalize_url, itu bukan URL
    assert set(plan.seen["ransomware_live"]) == {compute_dedup_key("ransomware_live", victim_key)}
    assert set(plan.seen["monitor_x"]) == {compute_dedup_key("monitor_x", "2054094495562559812")}


def test_real_registry_index_is_consistent() -> None:
    idx = ws.build_index()

    assert idx.by_script["cisacatalogThreat"] == "cisa_kev"
    assert idx.by_label["NEW ARTICLE FROM BITDEFENDER"] == "bitdefender"
    assert idx.by_source["cybersecurity news"] == "cybersecnews"  # alias
    assert "cisa_kev" in idx.article_scrapers and "ransomware_live" not in idx.article_scrapers
    assert "new_cve" not in idx.article_scrapers  # dedup dimatikan, upsert idempoten


# --- file offset lama (scraper Fase 10.E) ---------------------------------------------


def test_legacy_offset_files_are_read_by_their_shape(tmp_path) -> None:
    (tmp_path / "lines.txt").write_text("aaa\n\n  bbb  \n")
    (tmp_path / "adv.txt").write_text(
        '[{"LibrarySystem": "NPM", "AdvisoryID": "GHSA-1", "ModifiedDate": "2024-02-16"}]'
    )

    assert ws.legacy_offset_keys(tmp_path / "lines.txt", "lines") == ["aaa", "bbb"]
    assert ws.legacy_offset_keys(tmp_path / "adv.txt", "advisories") == ["GHSA-1:2024-02-16"]


def test_legacy_offsets_seed_the_new_scrapers_and_missing_files_leave_them_cold(tmp_path) -> None:
    (tmp_path / "ScraperNews/offset").mkdir(parents=True)
    (tmp_path / "ScraperNews/offset/APTattack_offset.txt").write_text("sha1\nsha2\n")
    (tmp_path / "techstackLibrary/offset").mkdir(parents=True)
    (tmp_path / "techstackLibrary/offset/techstack_npm_offset.txt").write_text(
        '[{"AdvisoryID": "GHSA-1", "ModifiedDate": "2024-02-16"}]'
    )  # pypi & golang sengaja tidak ada

    plan = ws.build_plan(MemoryDump({}), ws.build_index(), tmp_path)

    assert set(plan.seen["apt_ttp_simulation"]) == {
        compute_dedup_key("apt_ttp_simulation", "sha1"),
        compute_dedup_key("apt_ttp_simulation", "sha2"),
    }
    assert set(plan.seen["techstack_npm"]) == {
        compute_dedup_key("techstack_npm", "GHSA-1:2024-02-16")
    }
    assert "techstack_pypi" not in plan.seen and "techstack_go" not in plan.seen
    assert any("techstack_pypi" in n and "TIDAK ADA" in n for n in plan.legacy_notes)


def test_legacy_advisory_key_equals_the_key_the_real_scraper_emits() -> None:
    """Tanpa ini seed offset lama bisa diam-diam tidak pernah cocok."""
    from cti_scrapers.collectors.techstack_npm import TechstackNpm

    advisory = {"id": "GHSA-1", "modified": "2024-02-16T14:08:53.123456Z", "details": "d"}
    emitted = TechstackNpm()._notice("lodash", advisory).key

    assert emitted == ws.legacy_offset_keys_from_entry(
        {"AdvisoryID": "GHSA-1", "ModifiedDate": "2024-02-16"}
    )


def test_legacy_sha_key_equals_the_key_the_apt_scraper_emits() -> None:
    from cti_scrapers.collectors.apt_ttp_simulation import AptTtpSimulation

    from tests.unit.scraper_helpers import make_ctx

    summary = {"sha": "abc123", "commit": {"committer": {"date": "2026-09-25T10:00:00Z"}}}
    detail = {
        "commit": {"message": "m", "author": {"name": "a", "date": "2026-09-25T10:00:00Z"}},
        "files": [{"filename": "x.py", "status": "added", "additions": 1, "deletions": 0}],
    }
    ctx = make_ctx(AptTtpSimulation, lambda r: None)  # type: ignore[arg-type]

    [notice] = AptTtpSimulation().notices(ctx, summary, detail)

    assert notice.key == "abc123"


# --- penulisan -------------------------------------------------------------------------


@pytest.fixture
def session(_migrated_schema: None) -> Iterator[Session]:
    """Sesi savepoint -- sama dengan `test_runner.py` (Runner commit/rollback)."""
    from cti_core.db.engine import get_sync_engine

    connection = get_sync_engine().connect()
    connection.begin()
    s = Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
    try:
        yield s
    finally:
        s.close()
        connection.rollback()
        connection.close()


@pytest.fixture
def dispatched(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    seen: list[str] = []
    monkeypatch.setattr(
        "cti_scraper.runner.dispatch", lambda item, meta, session: seen.append(item.url)
    )
    return seen


def seeded_plan(urls: list[str], seen_at: datetime.datetime | None = None) -> ws.Plan:
    plan = ws.Plan()
    for url in urls:
        plan.add(SID, canonicalize_url(url), "offsets", seen_at)
    return plan


def test_write_plan_inserts_done_rows_with_the_scrapers_ttl(session: Session) -> None:
    plan = seeded_plan([A], seen_at=datetime.datetime(2026, 5, 1))  # naif -> UTC

    inserted = ws.write_plan(session, plan, index(), now=NOW)

    assert inserted == {SID: 1}
    row = session.scalars(select(ScraperSeen).where(ScraperSeen.scraper_id == SID)).one()
    assert (row.dedup_key, row.state, row.attempts, row.poisoned) == (key(A), "done", 1, False)
    assert row.lease_until is None
    assert row.first_seen_at == datetime.datetime(2026, 5, 1, tzinfo=datetime.UTC)
    assert row.committed_at == NOW
    assert row.expire_at == NOW + datetime.timedelta(days=30)  # ttl scraper, dari sekarang


def test_write_plan_is_idempotent(session: Session) -> None:
    plan = seeded_plan([A, B])

    first = ws.write_plan(session, plan, index(), now=NOW)
    second = ws.write_plan(session, plan, index(), now=NOW)

    assert first == {SID: 2} and second == {SID: 0}
    assert len(session.scalars(select(ScraperSeen)).all()) == 2


def test_write_plan_handles_more_rows_than_one_batch(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ws, "_BATCH", 3)
    plan = seeded_plan([f"https://foo.example/p/{n}" for n in range(8)])

    assert ws.write_plan(session, plan, index(), now=NOW) == {SID: 8}


# --- efek: Runner beneran ---------------------------------------------------------------------


def make_scraper(feed: Callable[[], list[Item]]) -> type[BaseScraper]:
    class _Scraper(BaseScraper):
        __abstract__ = True
        meta = ScraperMeta(id=SID, source="Foo", schedule="0 * * * *", max_items=50)

        def fetch(self, ctx: ScrapeContext) -> Iterator[Item]:
            yield from feed()

    return _Scraper


def articles(urls: list[str]) -> list[Item]:
    return [ArticleItem(title=f"t{i}", url=u) for i, u in enumerate(urls)]


def test_warm_scraper_skips_seeded_items_and_is_not_capped(
    session: Session, dispatched: list[str]
) -> None:
    """INTI 10.C. Feed: 4 item lama (ada di dump) + 3 item BARU sejak dump.
    Cap dingin = 2, jadi kalau scraper masih dianggap dingin cuma 2 yang lolos."""
    old = [f"https://foo.example/old/{n}" for n in range(4)]
    new = [f"https://foo.example/new/{n}" for n in range(3)]
    ws.write_plan(session, seeded_plan(old), index(), now=NOW)

    result = Runner(
        make_scraper(lambda: articles(old + new)), session=session, cold_start_max_items=2
    ).execute()

    assert result.status == "ok"
    assert result.items_found == 7
    assert sorted(dispatched) == sorted(new)  # KETIGA item baru lolos (bukan cuma 2)
    assert result.items_new == 3


def test_seeded_key_equals_the_key_runner_reserves(session: Session, dispatched: list[str]) -> None:
    """Tanpa seed, run pertama nge-reserve kunci yang sama persis dengan yang
    di-seed -- ini yang membuktikan rumus hash di script sama dengan runner."""
    Runner(make_scraper(lambda: articles([A])), session=session, cold_start_max_items=5).execute()
    reserved = set(
        session.scalars(select(ScraperSeen.dedup_key).where(ScraperSeen.scraper_id == SID))
    )

    assert reserved == set(seeded_plan([A]).seen[SID])


def test_cold_scraper_without_seed_is_still_capped(session: Session, dispatched: list[str]) -> None:
    """Kontrol negatif: tanpa warm start, feed yang sama kena cap -- jadi test
    di atas beneran membuktikan warm start, bukan kebetulan."""
    urls = [f"https://foo.example/x/{n}" for n in range(7)]

    Runner(make_scraper(lambda: articles(urls)), session=session, cold_start_max_items=2).execute()

    assert len(dispatched) == 2


# --- dump ASLI (kalau ada) ------------------------------------------------------------------

REAL_DUMP = pathlib.Path(__file__).resolve().parents[2] / "legacy" / "dump"
RETIRED = ("detectionEngineering", "sekoia", "paloaltonet", "validin", "DETECTION ENGINEERING",
           "SEKOIA", "PALO ALTO NET", "VALIDIN", "Detection Engineering", "Sekoia", "Validin",
           "Palo Alto Net", "unknown")  # fmt: skip


@pytest.mark.skipif(not REAL_DUMP.is_dir(), reason="legacy/dump tidak ada di checkout ini")
def test_real_dump_resolves_every_key_and_only_retired_sources_are_dropped(
    session: Session,
) -> None:
    """Pagar buat dump cutover: kalau dump terakhir bawa bentuk key baru yang
    gak bisa dipetakan, atau sumber yang gak dikenal, test ini (dan `--dry-run`)
    yang teriak -- bukan warm start yang diam-diam bolong."""
    pytest.importorskip("bson", reason="butuh `uv run --with pymongo`")

    idx = ws.build_index()
    plan = ws.build_plan(DirDump(REAL_DUMP), idx)

    assert plan.unresolved == {}
    assert all(any(r in name for r in RETIRED) for name in plan.dropped), dict(plan.dropped)
    assert set(plan.seen) <= set(idx.ttl_days)  # tiap kunci milik scraper yang ada
    assert sum(len(e) for e in plan.seen.values()) > 15_000

    written = ws.write_plan(session, plan, idx, now=NOW)
    assert written == {sid: len(e) for sid, e in plan.seen.items()}
    # scraper yang di-warm-start sekarang "hangat" -- gak akan kena cold-start cap
    from cti_core.db.repositories.scraper_seen import ScraperSeenRepo

    repo = ScraperSeenRepo(session)
    assert repo.has_any("cybersecnews") and repo.has_any("ransomware_live")
    assert not repo.has_any("crowdstrike")  # gak punya riwayat -> tetap dingin
