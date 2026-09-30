"""`CveMentionRepo` + `JobStateRepo` (Fase 10.E)."""

from __future__ import annotations

import datetime

from cti_core.db.models.report_state import SCOPE_NEWS, SCOPE_TWEET
from cti_core.db.repositories.report_state import CveMentionRepo, JobStateRepo
from sqlalchemy.orm import Session

D = datetime.date(2026, 9, 20)


def counts(repo: CveMentionRepo, scope: str = SCOPE_NEWS) -> dict[str, int]:
    return {m.cve_id: m.counter for m in repo.top(scope, limit=100)}


def test_bump_counts_every_occurrence_and_normalizes_case(db_session: Session) -> None:
    repo = CveMentionRepo(db_session)

    unique = repo.bump(SCOPE_NEWS, ["cve-2026-0001", "CVE-2026-0001", "cve-2026-0002", " "], on=D)

    assert unique == 2
    assert counts(repo) == {"CVE-2026-0001": 2, "CVE-2026-0002": 1}


def test_bump_accumulates_and_moves_last_seen_forward(db_session: Session) -> None:
    repo = CveMentionRepo(db_session)
    repo.bump(SCOPE_NEWS, ["cve-2026-0001"], on=D)

    repo.bump(SCOPE_NEWS, ["cve-2026-0001", "cve-2026-0001"], on=D + datetime.timedelta(days=3))

    [m] = repo.top(SCOPE_NEWS)
    assert (m.counter, m.last_seen_on) == (3, D + datetime.timedelta(days=3))


def test_top_orders_by_counter_then_id_and_honours_the_seen_since_window(
    db_session: Session,
) -> None:
    repo = CveMentionRepo(db_session)
    repo.bump(SCOPE_NEWS, ["cve-2026-0003"] * 2, on=D)
    repo.bump(SCOPE_NEWS, ["cve-2026-0002"] * 2, on=D)
    repo.bump(SCOPE_NEWS, ["cve-2026-0009"] * 5, on=D - datetime.timedelta(days=30))  # basi

    recent = [m.cve_id for m in repo.top(SCOPE_NEWS, seen_since=D - datetime.timedelta(days=7))]

    assert recent == ["CVE-2026-0002", "CVE-2026-0003"]  # seri -> urut id
    assert repo.top(SCOPE_NEWS)[0].cve_id == "CVE-2026-0009"  # tanpa jendela: terbesar


def test_reset_zeroes_the_counter_but_keeps_the_row_and_counting_restarts(
    db_session: Session,
) -> None:
    repo = CveMentionRepo(db_session)
    repo.bump(SCOPE_NEWS, ["cve-2026-0001"] * 4 + ["cve-2026-0002"], on=D)

    repo.reset(SCOPE_NEWS, ["cve-2026-0001"])

    assert counts(repo) == {"CVE-2026-0002": 1}  # yang 0 gak muncul di top
    repo.bump(SCOPE_NEWS, ["cve-2026-0001"], on=D)
    assert counts(repo)["CVE-2026-0001"] == 1  # mulai lagi dari 1, bukan 5


def test_scopes_are_independent(db_session: Session) -> None:
    repo = CveMentionRepo(db_session)
    repo.bump(SCOPE_NEWS, ["cve-2026-0001"] * 3, on=D)
    repo.bump(SCOPE_TWEET, ["cve-2026-0001"], on=D)

    repo.reset_scope(SCOPE_TWEET)

    assert counts(repo, SCOPE_NEWS) == {"CVE-2026-0001": 3}
    assert counts(repo, SCOPE_TWEET) == {}


def test_job_state_roundtrip_default_and_overwrite(db_session: Session) -> None:
    state = JobStateRepo(db_session)
    assert state.get("logbook.last_report_date") is None
    assert state.get("logbook.last_report_date", "belum") == "belum"

    state.set("logbook.last_report_date", "2026-09-12")
    state.set("cursor", {"tweet_id": "123"})
    state.set("logbook.last_report_date", "2026-09-26")

    assert state.get("logbook.last_report_date") == "2026-09-26"
    assert state.get("cursor") == {"tweet_id": "123"}
