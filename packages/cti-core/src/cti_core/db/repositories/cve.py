"""`CveTrackerRepo` -- satu-satunya jalur tulis `cve_tracker` (+ tabel anak
`cve_references`/`cve_affected`/`cve_pocs`). Gantiin dua penulis terpisah
di sistem lama (`newCveThreat.py` upsert penuh per-client, `githubPOCMonitor.py`
push POC ke array) -- di sini `upsert()` buat yang pertama, `add_pocs()`
buat yang kedua, dua-duanya lewat repo yang sama biar gak drift lagi.

`AsyncCveTrackerRepo`/`AsyncCveFalsePositiveRepo` (Fase 7.3, router `cve.py`)
BARU -- permukaan BACA + false-positive doang, satu-satunya jalur TULIS CVE
baru tetap `CveTrackerRepo` sync di atas (Celery task, Fase 4).

**Sengaja gak nyentuh `CveTicket`/`CveTicketItem`** (acknowledge/ticket
workflow) -- ketauan pas baca `cve_service.py`/`cve_ticket_service.py`
lama: `CveTicket` (Pydantic lama) itu record remediation KAYA per-CVE
(affected_asset, owner_email, remediation_status, escalation_required, dst
-- 14+ field), sedangkan model Postgres `CveTicket`/`CveTicketItem` (Fase 2)
didesain buat konsep BEDA (satu ticket_id + status, bisa nyakup BANYAK
cve_id lewat `CveTicketItem`, gak ada kolom `client_id`/`acknowledged_by`/
`acknowledge_time` sama sekali). Ini bukan "tambah kolom" kayak gap-gap
sebelumnya (`Role.display_name`, dst) -- butuh keputusan desain sendiri
soal bentuk final tabel, gak pantas diputus buru-buru di tengah porting
router lain. `ack_filter` (parameter list/stats lama) ikut di-skip karena
semantiknya nempel ticket ini."""

from __future__ import annotations

import datetime
from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from cti_core.db.models.article import Article
from cti_core.db.models.cve import (
    CveAffected,
    CveFalsePositive,
    CveNewsletterMention,
    CvePoc,
    CveReference,
    CveThreatActor,
    CveTracker,
    CveTTP,
)

_SORT_FIELDS = {
    "tech": CveTracker.tech,
    "severity": CveTracker.cve_score,
    "published": CveTracker.published,
}
"""`epss` (sort key lama) SENGAJA gak dipetakan -- gak ada kolom
`epss_score` di skema (fitur EPSS lookup ditunda, lihat router `cve.py`),
fallback ke `published` sama kayak default lama kalau key gak dikenal."""


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
            select(CveTracker).where(CveTracker.cve_id == cve_id, CveTracker.client_id == client_id)
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
        rows = (
            self.session.execute(select(CveTracker).where(CveTracker.cve_id == cve_id))
            .scalars()
            .all()
        )

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


def _apply_filters(
    stmt: Select[tuple[CveTracker]],
    *,
    client_id: str,
    tech: Sequence[str] | None,
    severity: Sequence[str] | None,
    search: str | None,
    date_start: datetime.date | None,
    date_end: datetime.date | None,
    exclude_cve_ids: Sequence[str] | None,
) -> Select[tuple[CveTracker]]:
    stmt = stmt.where(CveTracker.client_id == client_id)
    if exclude_cve_ids:
        stmt = stmt.where(CveTracker.cve_id.notin_(exclude_cve_ids))
    if tech:
        stmt = stmt.where(CveTracker.tech.in_(tech))
    if severity:
        stmt = stmt.where(CveTracker.cve_severity.in_([s.upper() for s in severity]))
    if search:
        stmt = stmt.where(
            or_(
                CveTracker.cve_id.ilike(f"%{search}%"),
                CveTracker.summary.ilike(f"%{search}%"),
                CveTracker.tech.ilike(f"%{search}%"),
            )
        )
    if date_start is not None:
        stmt = stmt.where(CveTracker.published >= date_start)
    if date_end is not None:
        stmt = stmt.where(CveTracker.published <= date_end)
    return stmt


class AsyncCveFalsePositiveRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_cve_ids(self, client_id: str) -> list[str]:
        result = await self.session.execute(
            select(CveFalsePositive.cve_id).where(CveFalsePositive.client_id == client_id)
        )
        return list(result.scalars().all())

    async def list_all_cve_ids(self) -> list[str]:
        """Lintas client, TANPA filter -- port apa adanya dari
        `cross_reference_service.py` (`db[FP_COLLECTION].distinct("cve_id")`,
        gak pernah nge-scope client). Dipakai `crossref` (Bagian 3) doang,
        endpoint FP utama (`cve.py`) tetap per-client via `list_cve_ids`."""
        result = await self.session.execute(select(CveFalsePositive.cve_id).distinct())
        return list(result.scalars().all())

    async def mark(self, cve_id: str, client_id: str, marked_by: str | None = None) -> None:
        existing = await self.session.execute(
            select(CveFalsePositive).where(
                CveFalsePositive.cve_id == cve_id, CveFalsePositive.client_id == client_id
            )
        )
        if existing.scalar_one_or_none() is not None:
            return
        self.session.add(CveFalsePositive(cve_id=cve_id, client_id=client_id, marked_by=marked_by))
        await self.session.flush()

    async def unmark(self, cve_id: str, client_id: str) -> None:
        result = await self.session.execute(
            select(CveFalsePositive).where(
                CveFalsePositive.cve_id == cve_id, CveFalsePositive.client_id == client_id
            )
        )
        row = result.scalar_one_or_none()
        if row is not None:
            await self.session.delete(row)
            await self.session.flush()

    async def bulk_mark(
        self, cve_ids: Sequence[str], client_id: str, marked_by: str | None = None
    ) -> int:
        existing = set(await self.list_cve_ids(client_id))
        to_add = [cid for cid in cve_ids if cid not in existing]
        for cid in to_add:
            self.session.add(CveFalsePositive(cve_id=cid, client_id=client_id, marked_by=marked_by))
        await self.session.flush()
        return len(to_add)


class AsyncCveTrackerRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_all_distinct_cve_ids(self) -> list[str]:
        """Lintas client, TANPA filter -- port `newsletter_service.
        _get_tp_cve_ids()` (Fase 7.3 Bagian 4), yang butuh SEMUA cve_id
        yang lagi ditrack buat nyaring "true positive" CVE mentions."""
        result = await self.session.execute(select(CveTracker.cve_id).distinct())
        return list(result.scalars().all())

    async def list_registered_on(
        self, day: datetime.date, *, exclude_cve_ids: Sequence[str], limit: int = 50
    ) -> list[CveTracker]:
        """Port `_collect_cves()` (`recap_service.py`, Fase 7.3 router
        `recap`, Bagian 5) -- CVE yang PERTAMA ke-track/kedetek/dipublish
        tanggal ini (OR tiga kolom tanggal, port apa adanya dari kode
        lama), lintas client (recap emang digest GLOBAL, bukan per-client).
        `exclude_cve_ids` global juga (bukan per-client) -- `recap` gak
        pernah nge-scope client sama sekali."""
        stmt = select(CveTracker).where(
            or_(
                func.date(CveTracker.registered_date) == day,
                func.date(CveTracker.detected_on) == day,
                CveTracker.published == day,
            )
        )
        if exclude_cve_ids:
            stmt = stmt.where(CveTracker.cve_id.not_in(exclude_cve_ids))
        stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_cve_id_any_client(self, cve_id: str) -> CveTracker | None:
        """Case-insensitive, lintas client, ambil SATU baris pertama yang
        cocok -- port apa adanya dari `cross_reference_service.get_cve_crossrefs()`
        (`find_one` tanpa client filter). Kalau CVE yang sama ke-track di
        lebih dari satu client, baris yang kepilih arbitrer (tergantung
        urutan default DB) -- sama ambiguitas kayak kode lama."""
        result = await self.session.execute(
            select(CveTracker).where(func.lower(CveTracker.cve_id) == cve_id.lower())
        )
        return result.scalars().first()

    async def add_newsletter_mention(
        self, cve_id: str, *, title: str, url: str, source: str, mention_date: str
    ) -> bool:
        """Port `cve_service.upsert_newsletter_mention()` -- `$push` dedup
        by url ke `cve_tracker.newsletter_mentions` (array Mongo) jadi
        insert ke tabel anak `cve_newsletter_mentions`, unique constraint
        (cve_tracker_id, url) yang jaga dedup-nya (bukan cek manual kayak
        `add_pocs`). Sama kayak `get_by_cve_id_any_client`, lintas client,
        ambil baris PERTAMA yang cocok -- kalau gak ketemu, no-op (return
        False), port apa adanya (`update_one` Mongo juga diam-diam no-op
        kalau filter gak match)."""
        cve = await self.get_by_cve_id_any_client(cve_id)
        if cve is None:
            return False
        existing_urls = {m.url for m in cve.newsletter_mentions}
        if url in existing_urls:
            return False
        cve.newsletter_mentions.append(
            CveNewsletterMention(title=title, url=url, source=source, mention_date=mention_date)
        )
        await self.session.flush()
        return True

    async def get_by_threat_actor_exact(
        self, actor_name: str, *, exclude_cve_ids: Sequence[str]
    ) -> list[CveTracker]:
        """Exact-match (case-insensitive) `threat_actors`, urut `cve_score`
        desc, limit 30 -- port `cross_reference_service.get_ta_crossrefs()`."""
        stmt = (
            select(CveTracker)
            .join(CveThreatActor)
            .where(func.lower(CveThreatActor.threat_actor) == actor_name.lower())
        )
        if exclude_cve_ids:
            stmt = stmt.where(CveTracker.cve_id.notin_(exclude_cve_ids))
        stmt = stmt.order_by(CveTracker.cve_score.desc().nulls_last()).limit(30)
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    async def search_crossref(
        self,
        *,
        threat_actors: Sequence[str],
        ttp_ids: Sequence[str],
        tech_list: Sequence[str],
        exclude_cve_ids: Sequence[str],
    ) -> list[CveTracker]:
        """CVE yang overlap TA/TTP/industri PIR -- port
        `cross_reference_service.get_pir_crossrefs()`. Kosongin ketiga
        kriteria (`threat_actors`/`ttp_ids`/`tech_list`) -> gak ada OR
        clause -> query balik ke `cve_id NOT IN fp` doang (match-all),
        port perilaku sama persis `cve_conditions = []` -> `$or` gak
        keisi di kode lama."""
        conditions = []
        if threat_actors:
            lowered = [t.lower() for t in threat_actors]
            conditions.append(
                CveTracker.id.in_(
                    select(CveThreatActor.cve_tracker_id).where(
                        func.lower(CveThreatActor.threat_actor).in_(lowered)
                    )
                )
            )
        if ttp_ids:
            conditions.append(
                CveTracker.id.in_(select(CveTTP.cve_tracker_id).where(CveTTP.ttp_id.in_(ttp_ids)))
            )
        if tech_list:
            conditions.append(CveTracker.tech.in_(tech_list))

        stmt = select(CveTracker)
        if exclude_cve_ids:
            stmt = stmt.where(CveTracker.cve_id.notin_(exclude_cve_ids))
        if conditions:
            stmt = stmt.where(or_(*conditions))
        stmt = stmt.order_by(CveTracker.cve_score.desc().nulls_last()).limit(50)
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    async def get_by_cve_ids(self, cve_ids: Sequence[str]) -> list[CveTracker]:
        """Lintas client, TANPA filter `client_id` -- port apa adanya dari
        `cross_reference_service.py`/`ta_profile_service.py` lama
        (`cve_col.find({"cve_id": {"$in": ...}})`, gak pernah nge-scope
        client). Dipakai `crossref`/`ta_groups` (Bagian 3), bukan
        endpoint CVE utama yang emang per-client. Kalau CVE yang sama ada
        di lebih dari satu client, caller yang mutusin gimana nanganin
        duplikat -- sama ambiguitas yang ada di kode lama, bukan
        diselesaikan diam-diam di sini."""
        if not cve_ids:
            return []
        result = await self.session.execute(
            select(CveTracker).where(CveTracker.cve_id.in_(cve_ids))
        )
        return list(result.scalars().all())

    async def list_filtered(
        self,
        *,
        client_id: str,
        page: int = 1,
        page_size: int = 20,
        tech: Sequence[str] | None = None,
        severity: Sequence[str] | None = None,
        search: str | None = None,
        date_start: datetime.date | None = None,
        date_end: datetime.date | None = None,
        exclude_cve_ids: Sequence[str] | None = None,
        sort_by: str = "published",
        sort_dir: str = "desc",
    ) -> tuple[list[CveTracker], int]:
        base = _apply_filters(
            select(CveTracker),
            client_id=client_id,
            tech=tech,
            severity=severity,
            search=search,
            date_start=date_start,
            date_end=date_end,
            exclude_cve_ids=exclude_cve_ids,
        )
        total = (
            await self.session.execute(select(func.count()).select_from(base.subquery()))
        ).scalar_one()

        order_col = _SORT_FIELDS.get(sort_by, CveTracker.published)
        order = order_col.desc() if sort_dir == "desc" else order_col.asc()
        list_stmt = (
            base.order_by(order.nulls_last()).offset((page - 1) * page_size).limit(page_size)
        )
        result = await self.session.execute(list_stmt)
        return list(result.scalars().all()), total

    async def get_stats(
        self,
        *,
        client_id: str,
        tech: Sequence[str] | None = None,
        severity: Sequence[str] | None = None,
        search: str | None = None,
        date_start: datetime.date | None = None,
        date_end: datetime.date | None = None,
        exclude_cve_ids: Sequence[str] | None = None,
    ) -> dict[str, int]:
        """`severity` SENGAJA cuma dipakai buat query `total` -- port perilaku
        lama: bucket critical/high/medium/low tetap ngitung SEMUA severity
        biar tetap bermakna dibandingin (filter severity bikin bucket lain
        selalu 0, gak ada gunanya)."""
        base_no_severity = _apply_filters(
            select(CveTracker),
            client_id=client_id,
            tech=tech,
            severity=None,
            search=search,
            date_start=date_start,
            date_end=date_end,
            exclude_cve_ids=exclude_cve_ids,
        )
        base_with_severity = _apply_filters(
            select(CveTracker),
            client_id=client_id,
            tech=tech,
            severity=severity,
            search=search,
            date_start=date_start,
            date_end=date_end,
            exclude_cve_ids=exclude_cve_ids,
        )

        async def _count(stmt: Select[tuple[CveTracker]]) -> int:
            result = await self.session.execute(select(func.count()).select_from(stmt.subquery()))
            return result.scalar_one()

        total = await _count(base_with_severity)
        critical = await _count(base_no_severity.where(CveTracker.cve_score >= 9.0))
        high = await _count(
            base_no_severity.where(CveTracker.cve_score >= 7.0, CveTracker.cve_score < 9.0)
        )
        medium = await _count(
            base_no_severity.where(CveTracker.cve_score >= 4.0, CveTracker.cve_score < 7.0)
        )
        low = await _count(
            base_no_severity.where(CveTracker.cve_score > 0, CveTracker.cve_score < 4.0)
        )
        return {"total": total, "critical": critical, "high": high, "medium": medium, "low": low}

    async def get_tech_list(self, client_id: str) -> list[str]:
        result = await self.session.execute(
            select(CveTracker.tech)
            .where(CveTracker.client_id == client_id, CveTracker.tech.is_not(None))
            .distinct()
            .order_by(CveTracker.tech)
        )
        return [t for t in result.scalars().all() if t]

    async def get_article_mentions(self, cve_ids: Sequence[str]) -> dict[str, list[dict[str, str]]]:
        """Port `get_article_mentions()` -- CVE ID nyebut di judul artikel
        mana aja. Query SATU kali (OR ilike per cve_id), bukan N query."""
        result: dict[str, list[dict[str, str]]] = {cid: [] for cid in cve_ids}
        if not cve_ids:
            return result
        stmt = select(Article.title, Article.url).where(
            or_(*[Article.title.ilike(f"%{cid}%") for cid in cve_ids])
        )
        rows = (await self.session.execute(stmt)).all()
        for title, url in rows:
            for cid in cve_ids:
                if cid.upper() in title.upper():
                    result[cid].append({"title": title, "url": url})
        return result

    async def purge_orphaned(
        self, *, client_id: str, active_tech_names: Sequence[str], dry_run: bool = True
    ) -> dict[str, Any]:
        """Port `purge_orphaned_cves()`. `active_tech_names` kosong = SEMUA
        CVE client ini dianggap orphan (port perilaku lama persis --
        client tanpa tech stack sama sekali gak punya CVE yang "sah")."""
        stmt = select(CveTracker).where(CveTracker.client_id == client_id)
        if active_tech_names:
            stmt = stmt.where(CveTracker.tech.notin_(active_tech_names))
        rows = (await self.session.execute(stmt)).scalars().all()

        by_tech: dict[str, int] = {}
        cve_ids: list[str] = []
        for row in rows:
            t = row.tech or "(no tech)"
            by_tech[t] = by_tech.get(t, 0) + 1
            cve_ids.append(row.cve_id)

        if dry_run or not rows:
            return {
                "dry_run": True,
                "would_delete": len(cve_ids),
                "by_tech": by_tech,
                "cve_ids": cve_ids,
            }

        for row in rows:
            await self.session.delete(row)
        fp_stmt = select(CveFalsePositive).where(
            CveFalsePositive.client_id == client_id, CveFalsePositive.cve_id.in_(cve_ids)
        )
        for fp in (await self.session.execute(fp_stmt)).scalars().all():
            await self.session.delete(fp)
        await self.session.flush()
        return {"dry_run": False, "deleted": len(cve_ids), "by_tech": by_tech, "cve_ids": cve_ids}
