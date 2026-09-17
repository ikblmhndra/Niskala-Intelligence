"""CveTrackerRepo -- satu-satunya jalur tulis `cve_tracker` (+ tabel anak
`cve_references`/`cve_affected`/`cve_pocs`). Gantiin dua penulis terpisah
di sistem lama (`newCveThreat.py` upsert penuh per-client, `githubPOCMonitor.py`
push POC ke array) -- di sini `upsert()` buat yang pertama, `add_pocs()`
buat yang kedua, dua-duanya lewat repo yang sama biar gak drift lagi.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from cti_core.db.models.cve import CveAffected, CvePoc, CveReference, CveTracker


class CveTrackerRepo:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert(
        self,
        *,
        cve_id: str,
        client_id: str,
        references: Sequence[str] = (),
        affected: Sequence[str] = (),
        **fields: Any,
    ) -> CveTracker:
        """`references`/`affected` SELALU diganti utuh (bukan di-merge) --
        MITRE ngasih daftar lengkap tiap kali, bukan delta. Relationship-nya
        `cascade="all, delete-orphan"` (lihat model), jadi assign list baru
        otomatis buang baris anak yang lama."""
        existing = self.session.execute(
            select(CveTracker).where(
                CveTracker.cve_id == cve_id, CveTracker.client_id == client_id
            )
        ).scalar_one_or_none()

        if existing is None:
            row = CveTracker(cve_id=cve_id, client_id=client_id, **fields)
            row.references = [CveReference(url=u) for u in references]
            row.affected = [CveAffected(affected=a) for a in affected]
            self.session.add(row)
            self.session.flush()
            return row

        for k, v in fields.items():
            setattr(existing, k, v)
        existing.references = [CveReference(url=u) for u in references]
        existing.affected = [CveAffected(affected=a) for a in affected]
        self.session.flush()
        return existing

    def add_pocs(self, *, cve_id: str, pocs: list[dict[str, str]]) -> int:
        """Nambahin POC baru ke SEMUA baris `cve_tracker` yang `cve_id`-nya
        cocok -- satu CVE bisa dipantau lebih dari satu client, masing-masing
        baris sendiri (lihat unique constraint `(cve_id, client_id)`).
        Skip URL yang udah tercatat (setara `existing_poc_urls` di
        `githubPOCMonitor.py` lama). Balikin jumlah baris yang KE-UPDATE
        (bukan jumlah POC)."""
        rows = self.session.execute(
            select(CveTracker).where(CveTracker.cve_id == cve_id)
        ).scalars().all()

        updated = 0
        for row in rows:
            existing_urls = {p.url for p in row.pocs}
            new_pocs = [p for p in pocs if p["url"] not in existing_urls]
            if not new_pocs:
                continue
            row.pocs.extend(
                CvePoc(url=p["url"], source=p.get("source"), poc_type=p.get("poc_type"))
                for p in new_pocs
            )
            row.poc_available = True
            updated += 1

        self.session.flush()
        return updated
