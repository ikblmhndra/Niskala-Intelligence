"""`tools/seed/fase10_cve_migrate.py` -- migrasi `cve_tracker`/`cve_false_positives`/
`cve_tickets` dari dump Mongo lama (Fase 10.F, permintaan user 2026-09-30).

Yang dikunci:
  1. Bentuk dump lama (`reference`/`affected` dict, `cisa_kev_*` rata, timestamp naive WIB) ->
     kolom skema baru -- kalau salah satu berubah bentuk diam-diam, migrasi bisa "berhasil" tapi
     datanya salah (bukan error keras).
  2. Idempoten: CVE yang SUDAH ADA (mis. `new_cve` sudah jalan duluan) dilewati, TIDAK ditimpa,
     dan anak-tabelnya (reference/affected/poc) TIDAK didobel.
  3. `client_id` yang tidak ada di `clients` dilewati dengan pesan, bukan bikin migrasi gagal
     total (FK violation) atau diam-diam nyipta client.
"""

from __future__ import annotations

import datetime
import pathlib
from collections.abc import Iterator

import pytest
from cti_core.db.models.auth import Client
from cti_core.db.models.cve import (
    CveAffected,
    CveFalsePositive,
    CveReference,
    CveTicket,
    CveTracker,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from tools.seed import fase10_cve_migrate as mig
from tools.seed._dump import DirDump, MemoryDump

REAL_DUMP = pathlib.Path(__file__).resolve().parents[2] / "legacy" / "dump"


@pytest.fixture
def session(db_session: Session) -> Iterator[Session]:
    db_session.add(Client(client_id="default", name="Default"))
    db_session.flush()
    yield db_session


def cve_doc(**over: object) -> dict:
    base: dict = {
        "cve_id": "CVE-2026-1111",
        "client_id": "default",
        "tech": "nginx",
        "link": "https://nvd.nist.gov/vuln/detail/CVE-2026-1111",
        "summary": "ringkasan",
        "published": "2026-04-21T16:48:24.722Z",
        "solutions": "No solution yet",
        "cve_score": 9.8,
        "cve_severity": "CRITICAL",
        "cvss_vector": "CVSS:3.1/AV:N",
        "cve_modified_date": "2026-04-22T00:00:00.000Z",
        "poc_available": False,
        "detected_on": "2026-04-26 19:20:38",
        "reference": [],
        "affected": [],
        "pocs": [],
    }
    base.update(over)
    return base


def dump_of(**collections: list[dict]) -> MemoryDump:
    return MemoryDump({name.replace("__", "/"): docs for name, docs in collections.items()})


def one_cve(session: Session) -> CveTracker:
    return session.scalars(select(CveTracker)).one()


# --- perencanaan + penulisan: cve_tracker -------------------------------------------------------


def test_a_new_cve_is_inserted_with_its_children(session: Session) -> None:
    dump = dump_of(
        news_db__cve_tracker=[
            cve_doc(
                reference=[{"url": "https://a.example/adv", "tags": ""}],
                affected=[{"palo alto": ["< 2.0", "<= 1.9"]}],
                pocs=[{"url": "https://github.com/x/y", "source": "x", "type": "poc"}],
            )
        ]
    )
    plan = mig.build_plan(dump, {"default"})

    counts = mig.write_plan(session, plan)

    assert counts == {
        "cve_tracker": 1,
        "cve_references": 1,
        "cve_affected": 2,
        "cve_pocs": 1,
        "cve_false_positives": 0,
        "cve_tickets": 0,
    }
    row = one_cve(session)
    assert (row.cve_id, row.client_id, row.tech) == ("CVE-2026-1111", "default", "nginx")
    assert [r.url for r in row.references] == ["https://a.example/adv"]
    # "palo alto" (multi-kata) TIDAK ter-encode -- dan format SAMA dengan `_new_cve.py`:
    # "<product>: <constraint>", satu baris per constraint (bukan satu baris per product).
    assert sorted(a.affected for a in row.affected) == ["palo alto: < 2.0", "palo alto: <= 1.9"]
    assert [(p.url, p.source, p.poc_type) for p in row.pocs] == [
        ("https://github.com/x/y", "x", "poc")
    ]


def test_multi_word_tech_is_copied_as_is_not_url_encoded(session: Session) -> None:
    """Field ini di-copy apa adanya (bukan dicocokkan ke techstack) -- TIDAK kena bug
    `_new_cve.py` (pencocokan tech "palo%20alto" vs "palo alto") sama sekali."""
    dump = dump_of(news_db__cve_tracker=[cve_doc(tech="microsoft 365")])
    plan = mig.build_plan(dump, {"default"})

    mig.write_plan(session, plan)

    assert one_cve(session).tech == "microsoft 365"


def test_cisa_kev_flat_fields_become_one_detail_dict(session: Session) -> None:
    dump = dump_of(
        news_db__cve_tracker=[
            cve_doc(
                cisa_kev=True,
                cisa_kev_name="Foo RCE",
                cisa_kev_vendor="Foo Inc",
                cisa_kev_product="Foo Server",
                cisa_kev_description="desc",
                cisa_kev_date_added="2026-05-01",
                cisa_kev_due_date="2026-05-15",
                cisa_kev_action="Apply update",
            )
        ]
    )
    plan = mig.build_plan(dump, {"default"})

    mig.write_plan(session, plan)

    row = one_cve(session)
    assert row.cisa_kev is True
    assert row.cisa_kev_detail == {
        "name": "Foo RCE",
        "vendor": "Foo Inc",
        "product": "Foo Server",
        "description": "desc",
        "date_added": "2026-05-01",
        "due_date": "2026-05-15",
        "action": "Apply update",
    }


def test_missing_boolean_and_optional_fields_default_safely(session: Session) -> None:
    doc = cve_doc()
    for f in ("cisa_kev", "active_exploitation", "epss_score", "epss_percentile"):
        doc.pop(f, None)
    plan = mig.build_plan(dump_of(news_db__cve_tracker=[doc]), {"default"})

    mig.write_plan(session, plan)

    row = one_cve(session)
    assert (row.cisa_kev, row.active_exploitation) == (False, False)
    assert row.epss_score is None and row.cisa_kev_detail == {}


def test_naive_timestamps_are_interpreted_as_wib_not_utc(session: Session) -> None:
    """`detected_on` naive "YYYY-MM-DD HH:MM:SS" -- SAMA asumsi dengan
    `WORKER__REPORT_UTC_OFFSET_HOURS=7` yang sudah dipakai di seluruh Fase 10."""
    plan = mig.build_plan(
        dump_of(news_db__cve_tracker=[cve_doc(detected_on="2026-04-26 19:20:38")]), {"default"}
    )

    mig.write_plan(session, plan)

    assert one_cve(session).detected_on == datetime.datetime(
        2026, 4, 26, 12, 20, 38, tzinfo=datetime.UTC
    )  # 19:20 WIB == 12:20 UTC


def test_explicit_z_and_offset_timestamps_are_used_as_is_not_reinterpreted(
    session: Session,
) -> None:
    plan = mig.build_plan(
        dump_of(news_db__cve_tracker=[cve_doc(published="2026-04-21T16:48:24.722Z")]), {"default"}
    )

    mig.write_plan(session, plan)

    assert one_cve(session).published == datetime.date(2026, 4, 21)  # bukan digeser 7 jam


def test_existing_cve_for_the_same_client_is_left_untouched_no_duplicate_children(
    session: Session,
) -> None:
    session.add(CveTracker(cve_id="CVE-2026-1111", client_id="default", tech="ALREADY-HERE"))
    session.flush()

    plan = mig.build_plan(
        dump_of(
            news_db__cve_tracker=[
                cve_doc(tech="from-dump", reference=[{"url": "https://x.example", "tags": ""}])
            ]
        ),
        {"default"},
    )
    counts = mig.write_plan(session, plan)

    assert counts["cve_tracker"] == 0
    row = one_cve(session)
    assert row.tech == "ALREADY-HERE"  # TIDAK ditimpa
    assert row.references == []  # anak tabel TIDAK ditambahkan buat baris yang dilewati


def test_running_migration_twice_does_not_duplicate_anything(session: Session) -> None:
    plan = mig.build_plan(
        dump_of(
            news_db__cve_tracker=[
                cve_doc(
                    reference=[{"url": "https://a.example", "tags": ""}],
                    affected=[{"nginx": ["< 2.0"]}],
                )
            ]
        ),
        {"default"},
    )

    first = mig.write_plan(session, plan)
    session.flush()
    second = mig.write_plan(session, plan)

    assert first["cve_tracker"] == 1 and second["cve_tracker"] == 0
    assert len(session.scalars(select(CveTracker)).all()) == 1
    assert len(session.scalars(select(CveReference)).all()) == 1
    assert len(session.scalars(select(CveAffected)).all()) == 1


# --- false positives + tickets -------------------------------------------------------------------


def test_false_positive_is_migrated_and_idempotent(session: Session) -> None:
    doc = {
        "cve_id": "CVE-2026-1111",
        "client_id": "default",
        "marked_at": "2026-04-29T07:45:53.339654",
    }
    plan = mig.build_plan(dump_of(news_db__cve_false_positives=[doc]), {"default"})

    first = mig.write_plan(session, plan)
    second = mig.write_plan(session, plan)

    assert first["cve_false_positives"] == 1 and second["cve_false_positives"] == 0
    row = session.scalars(select(CveFalsePositive)).one()
    assert row.cve_id == "CVE-2026-1111"
    assert row.marked_at == datetime.datetime(2026, 4, 29, 0, 45, 53, 339654, tzinfo=datetime.UTC)


def test_false_positive_without_client_id_defaults_to_default(session: Session) -> None:
    """17/20 dokumen di dump asli punya `client_id`, 3 tidak -- default lama = `"default"`."""
    doc = {"cve_id": "CVE-2026-2222", "marked_at": "2026-04-29T07:45:53"}
    plan = mig.build_plan(dump_of(news_db__cve_false_positives=[doc]), {"default"})

    mig.write_plan(session, plan)

    assert session.scalars(select(CveFalsePositive)).one().client_id == "default"


def test_false_positive_missing_marked_at_falls_back_to_now_not_null(session: Session) -> None:
    """`marked_at` NOT NULL tanpa default Python -- kalau field-nya kosong/hilang di dump dan
    fallback ini gak ada, INSERT bakal ngirim NULL eksplisit dan kena constraint DB, bukan
    dilewatkan diam-diam."""
    doc = {"cve_id": "CVE-2026-3333", "client_id": "default"}  # marked_at sengaja tak ada
    plan = mig.build_plan(dump_of(news_db__cve_false_positives=[doc]), {"default"})

    mig.write_plan(session, plan)

    assert session.scalars(select(CveFalsePositive)).one().marked_at is not None


def test_ticket_fields_map_across_and_reported_date_is_dropped(session: Session) -> None:
    doc = {
        "cve_id": "CVE-2026-1111",
        "client_id": "default",
        "ticket_id": "CTI-2026-04-004",
        "acknowledged_by": "Michael",
        "acknowledge_time": "2026-04-29 17:21:21",
        "affected_asset": "web-01",
        "remediation_status": "In Progress",
        "risk_acceptance": "",
        "escalation_required": True,
        "remediation_date_plan": "2026-07-24",
        "cve_reported_date": "2026-04-29 17:43:44",  # SENGAJA tidak ada kolomnya -- harus diabaikan
    }
    plan = mig.build_plan(dump_of(news_db__cve_tickets=[doc]), {"default"})

    counts = mig.write_plan(session, plan)

    assert counts["cve_tickets"] == 1
    row = session.scalars(select(CveTicket)).one()
    assert row.ticket_id == "CTI-2026-04-004"
    assert row.acknowledged_by == "Michael"
    assert row.acknowledge_time == datetime.datetime(2026, 4, 29, 10, 21, 21, tzinfo=datetime.UTC)
    assert row.affected_asset == "web-01"
    assert row.remediation_status == "In Progress"
    assert row.risk_acceptance is None  # string kosong -> NULL, bukan ""
    assert row.escalation_required is True
    assert row.remediation_date_plan == datetime.date(2026, 7, 24)
    assert not hasattr(row, "cve_reported_date")


def test_ticket_id_from_the_dump_is_kept_as_is_no_renumbering(session: Session) -> None:
    doc = {
        "cve_id": "CVE-2026-1111",
        "client_id": "default",
        "ticket_id": "CTI-2026-09-139",
        "acknowledged_by": "a",
        "acknowledge_time": "2026-09-15 10:00:00",
    }
    plan = mig.build_plan(dump_of(news_db__cve_tickets=[doc]), {"default"})

    mig.write_plan(session, plan)

    assert session.scalars(select(CveTicket)).one().ticket_id == "CTI-2026-09-139"


def test_duplicate_ticket_docs_for_the_same_pair_keep_the_latest_acknowledge_time(
    session: Session,
) -> None:
    """Ketemu di dump asli: 11 pasangan (cve_id, client_id) punya 2 dokumen tiket -- dump lama
    tidak punya unique index seperti skema baru. Analis yang sama acknowledge dua kali beda
    menit; yang menang harus yang PALING BARU, bukan yang pertama muncul di file (urutan
    insersi Mongo, bukan urutan waktu acknowledge -- dump asli urutannya kebalik untuk
    beberapa pasangan)."""
    older = {
        "cve_id": "CVE-2026-1111",
        "client_id": "default",
        "ticket_id": "CTI-2026-05-008",
        "acknowledge_time": "2026-05-20 16:09:55",
    }
    newer = {
        "cve_id": "CVE-2026-1111",
        "client_id": "default",
        "ticket_id": "CTI-2026-05-031",
        "acknowledge_time": "2026-05-20 16:45:16",
    }

    for first, second in ((older, newer), (newer, older)):  # urutan file gak boleh nentuin hasil
        plan = mig.build_plan(dump_of(news_db__cve_tickets=[first, second]), {"default"})

        assert len(plan.tickets) == 1 and plan.duplicate_tickets_dropped == 1
        assert plan.tickets[0]["ticket_id"] == "CTI-2026-05-031"

        mig.write_plan(session, plan)
        row = session.scalars(select(CveTicket)).one()
        assert row.ticket_id == "CTI-2026-05-031"
        session.delete(row)
        session.flush()


def test_running_ticket_migration_twice_does_not_duplicate(session: Session) -> None:
    doc = {
        "cve_id": "CVE-2026-1111",
        "client_id": "default",
        "ticket_id": "CTI-2026-04-004",
        "acknowledged_by": "a",
        "acknowledge_time": "2026-04-29 17:21:21",
    }
    plan = mig.build_plan(dump_of(news_db__cve_tickets=[doc]), {"default"})

    mig.write_plan(session, plan)
    mig.write_plan(session, plan)

    assert len(session.scalars(select(CveTicket)).all()) == 1


# --- client tidak dikenal ------------------------------------------------------------------------


def test_docs_for_an_unknown_client_are_skipped_not_crashed(session: Session) -> None:
    plan = mig.build_plan(
        dump_of(news_db__cve_tracker=[cve_doc(client_id="ghost-client")]), {"default"}
    )

    assert plan.skipped_no_client == {"ghost-client"}
    counts = mig.write_plan(session, plan)
    assert counts["cve_tracker"] == 0
    assert session.scalars(select(CveTracker)).all() == []


# --- regresi terhadap dump asli --------------------------------------------------------------


@pytest.mark.skipif(not REAL_DUMP.is_dir(), reason="legacy/dump tidak ada di checkout ini")
def test_real_dump_migrates_without_crashing_and_matches_known_counts(session: Session) -> None:
    """Pagar buat dump cutover: kalau bentuk dump berubah (field baru/hilang), test ini yang
    teriak duluan -- bukan migrasi yang diam-diam salah baca di produksi."""
    pytest.importorskip("bson", reason="butuh `uv run --with pymongo`")

    plan = mig.build_plan(DirDump(REAL_DUMP), {"default"})

    assert len(plan.cves) == 575
    assert len(plan.false_positives) == 20
    # 505 dokumen tiket, tapi 11 pasangan (cve_id, client_id) punya 2 dokumen (dump lama gak
    # punya unique index seperti skema baru) -- dedup ke yang acknowledge_time-nya paling baru.
    assert len(plan.tickets) == 494
    assert plan.duplicate_tickets_dropped == 11
    assert plan.skipped_no_client == set()

    counts = mig.write_plan(session, plan)

    assert counts["cve_tracker"] == 575
    assert counts["cve_false_positives"] == 20
    assert counts["cve_tickets"] == 494
    assert session.scalars(select(CveTracker).where(CveTracker.tech == "microsoft 365")).first()
