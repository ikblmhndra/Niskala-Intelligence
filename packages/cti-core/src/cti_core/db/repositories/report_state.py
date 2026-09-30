"""Repository `cve_mentions` + `job_state` (Fase 10.E). Sync-only: pemakainya
pipeline enrichment dan task Celery, bukan API."""

from __future__ import annotations

import datetime
from collections import Counter
from collections.abc import Iterable
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from cti_core.db.models.report_state import CveMention, JobState


class CveMentionRepo:
    def __init__(self, session: Session) -> None:
        self.session = session

    def bump(self, scope: str, cve_ids: Iterable[str], *, on: datetime.date) -> int:
        """Tambah counter tiap CVE (kemunculan ganda dihitung ganda, sama dengan
        `update_cve_mention` lama yang dipanggil sekali per kemunculan) dan set
        `last_seen_on`. Satu upsert per CVE unik. Return jumlah CVE unik."""
        counts = Counter(c.strip().upper() for c in cve_ids if c and c.strip())
        for cve_id, n in counts.items():
            stmt = pg_insert(CveMention).values(
                scope=scope, cve_id=cve_id, counter=n, last_seen_on=on
            )
            stmt = stmt.on_conflict_do_update(
                constraint="uq_cve_mentions_scope_cve",
                set_={"counter": CveMention.counter + n, "last_seen_on": on},
            )
            self.session.execute(stmt)
        self.session.flush()
        return len(counts)

    def top(
        self, scope: str, *, seen_since: datetime.date | None = None, limit: int = 50
    ) -> list[CveMention]:
        """Counter > 0, urut counter turun (lalu CVE id, biar deterministik).
        `seen_since`: cuma yang `last_seen_on >= seen_since`."""
        stmt = select(CveMention).where(CveMention.scope == scope, CveMention.counter > 0)
        if seen_since is not None:
            stmt = stmt.where(CveMention.last_seen_on >= seen_since)
        stmt = stmt.order_by(CveMention.counter.desc(), CveMention.cve_id).limit(limit)
        return list(self.session.scalars(stmt))

    def reset(self, scope: str, cve_ids: Iterable[str]) -> None:
        """Counter -> 0 (baris dipertahankan) buat CVE yang baru dilaporkan."""
        ids = [c.upper() for c in cve_ids]
        if not ids:
            return
        self.session.execute(
            update(CveMention)
            .where(CveMention.scope == scope, CveMention.cve_id.in_(ids))
            .values(counter=0)
        )
        self.session.flush()

    def reset_scope(self, scope: str) -> None:
        self.session.execute(update(CveMention).where(CveMention.scope == scope).values(counter=0))
        self.session.flush()


class JobStateRepo:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, key: str, default: Any = None) -> Any:
        row = self.session.get(JobState, key)
        return default if row is None else row.value

    def set(self, key: str, value: Any) -> None:
        stmt = pg_insert(JobState).values(key=key, value=value)
        self.session.execute(
            stmt.on_conflict_do_update(index_elements=["key"], set_={"value": stmt.excluded.value})
        )
        self.session.flush()
