"""Migrasi CVE tracker dari dump Mongo lama (Fase 10.F, permintaan user 2026-09-30): isi
`cve_tracker`/`cve_false_positives`/`cve_tickets` dari `news_db.cve_tracker` +
`news_db.cve_false_positives` + `news_db.cve_tickets`, supaya CVE Tracker TIDAK kosong di hari
pertama cutover.

Bukan pembalikan keputusan "mulai dari DB kosong" (plan §"Cutover") -- itu keputusan buat 38
collection yang datanya besar dan skema-nya beda jauh. CVE tracker beda kasus: dump-nya kecil
(575 CVE + 20 FP + 505 ticket per rehearsal 2026-09-30) dan field-nya map hampir 1:1 ke skema
Postgres baru (dicek manual, bukan tebakan):

  - `cve_tracker.tech` sumbernya SUDAH nama asli ("microsoft 365", bukan "microsoft%20365") --
    TIDAK kena bug yang dibenerin di `_new_cve.py` (dedup/pencocokan tech multi-kata), karena
    field ini di-copy apa adanya, bukan dicocokkan ke techstack.
  - `reference`: list `{"url","tags"}` -> `CveReference.url` (`tags` gak ada kolomnya di skema
    baru, dibuang -- gak pernah dipakai UI mana pun, dicek grep).
  - `affected`: list `{"<product>": ["<constraint>", ...]}` -> satu `CveAffected.affected` per
    constraint, format STRING SAMA dengan yang di-generate `_new_cve.py` (`f"{product}: {c}"`) --
    biar baris migrasi dan baris hasil scraper gak bisa dibedain formatnya.
  - `pocs`: list `{"url","source","type"}` -> `CvePoc(url, source, poc_type)`
    (`type` -> `poc_type`).
  - `cisa_kev_{name,vendor,product,description,date_added,due_date,action}` (field rata di dump
    lama) -> satu dict `CveTracker.cisa_kev_detail` (bentuk JSONB yang dipakai `cve_lookup.py`).
  - `cve_tickets`: field UI baru (`affected_asset`, `remediation_status`, `risk_acceptance`, dst)
    SUDAH ADA di 460/505 dokumen dump -- bukan cuma placeholder kosong, jadi ikut dimigrasi.
    `cve_reported_date` SENGAJA TIDAK dimigrasi (skema baru menghapus kolom ini sendiri --
    lihat docstring `CveTicket`, nilainya dibaca dari `CveTracker.published` saat serialize).
    `ticket_id` (`"CTI-2026-09-139"`) dipakai APA ADANYA -- `get_next_ticket_id()` cuma nge-scan
    prefix BULAN BERJALAN, jadi nomor lama gak akan bentrok sama nomor baru yang dibuat nanti.

Timestamp naive (`detected_on`/`registered_date`/`acknowledge_time`, format
`"YYYY-MM-DD HH:MM:SS"`) diasumsikan WIB (+07:00) -- SAMA asumsi dengan
`WORKER__REPORT_UTC_OFFSET_HOURS=7` yang sudah dipakai di seluruh Fase 10 buat timestamp lokal
sistem lama. Field bertanda `Z`/offset eksplisit dipakai apa adanya (tidak ditebak).

Idempoten: `ON CONFLICT (cve_id, client_id) DO NOTHING` di ketiga tabel. CVE yang sudah ada (mis.
`new_cve` sudah sempat jalan duluan buat CVE yang sama) DILEWATI apa adanya -- migrasi ini
mengisi yang KOSONG, bukan menimpa data yang lebih baru. Aman dijalankan ulang.

Jalankan SETELAH `fase10_reference_data.py` (client harus sudah ada -- FK `client_id`).

    uv run --with pymongo python tools/seed/fase10_cve_migrate.py --dry-run
    uv run --with pymongo python tools/seed/fase10_cve_migrate.py
"""

from __future__ import annotations

import argparse
import datetime
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cti_core.db.engine import sync_session
from cti_core.db.models.auth import Client
from cti_core.db.models.cve import (
    CveAffected,
    CveFalsePositive,
    CvePoc,
    CveReference,
    CveTicket,
    CveTracker,
)
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

if __package__ in (None, ""):  # dijalankan sebagai skrip: `python tools/seed/...`
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.seed._dump import DEFAULT_DUMP_DIR, DirDump, Dump, DumpError

_WIB = datetime.timezone(datetime.timedelta(hours=7))
_CISA_KEV_FIELD_MAP = {
    "cisa_kev_date_added": "date_added",
    "cisa_kev_due_date": "due_date",
    "cisa_kev_vendor": "vendor",
    "cisa_kev_product": "product",
    "cisa_kev_name": "name",
    "cisa_kev_description": "description",
    "cisa_kev_action": "action",
}


def parse_dt(raw: Any, *, assume_wib: bool = False) -> datetime.datetime | None:
    """ISO dengan `Z`/offset dipakai apa adanya (`datetime.fromisoformat` Python 3.12 sudah
    menangani suffix `Z` sendiri -- proyek ini `requires-python = ">=3.12"`, jadi tidak perlu
    normalisasi manual). Naive (tanpa offset) diasumsikan WIB kalau `assume_wib`, kalau tidak
    UTC. `None`/string kosong -> `None`."""
    if not raw:
        return None
    try:
        dt = datetime.datetime.fromisoformat(str(raw).strip())
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_WIB if assume_wib else datetime.UTC)
    return dt


def parse_date(raw: Any, *, assume_wib: bool = False) -> datetime.date | None:
    dt = parse_dt(raw, assume_wib=assume_wib)
    return dt.date() if dt else None


def flatten_affected(raw: list[dict[str, Any]]) -> list[str]:
    """`[{"palo alto": ["< 2.0", "<= 1.9"]}]` -> `["palo alto: < 2.0", "palo alto: <= 1.9"]` --
    format string SAMA dengan yang di-generate `_new_cve.py` (bukan port literal bentuk dict)."""
    out: list[str] = []
    for entry in raw:
        for product, constraints in entry.items():
            for c in constraints or []:
                out.append(f"{product}: {c}")
    return out


def cisa_kev_detail(doc: dict[str, Any]) -> dict[str, Any]:
    return {new: doc[old] for old, new in _CISA_KEV_FIELD_MAP.items() if doc.get(old)}


@dataclass
class Row:
    cve: dict[str, Any]
    references: list[str]
    affected: list[str]
    pocs: list[dict[str, str | None]]


@dataclass
class Plan:
    cves: list[Row] = field(default_factory=list)
    false_positives: list[dict[str, Any]] = field(default_factory=list)
    tickets: list[dict[str, Any]] = field(default_factory=list)
    skipped_no_client: set[str] = field(default_factory=set)
    duplicate_tickets_dropped: int = 0
    """Dump lama TIDAK punya unique index (cve_id, client_id) di `cve_tickets` -- ketemu 11
    pasangan dengan 2 dokumen (analis yang sama, acknowledge dua kali beda menit; skema baru
    UNIQUE-kan pasangan ini). Yang `acknowledge_time`-nya PALING BARU menang, bukan yang
    pertama ketemu di file (urutan dump = urutan insersi Mongo, bukan urutan waktu acknowledge)."""


def build_plan(dump: Dump, known_clients: set[str]) -> Plan:
    plan = Plan()

    for doc in dump.docs("news_db/cve_tracker"):
        client_id = str(doc.get("client_id") or "default")
        if client_id not in known_clients:
            plan.skipped_no_client.add(client_id)
            continue
        cve = {
            "cve_id": doc["cve_id"],
            "client_id": client_id,
            "tech": doc.get("tech"),
            "link": doc.get("link"),
            "summary": doc.get("summary"),
            "published": parse_date(doc.get("published")),
            "solutions": doc.get("solutions"),
            "cve_score": doc.get("cve_score"),
            "cve_severity": doc.get("cve_severity"),
            "cvss_vector": doc.get("cvss_vector"),
            "cve_modified_date": parse_date(doc.get("cve_modified_date")),
            "poc_available": bool(doc.get("poc_available", False)),
            "cisa_kev": bool(doc.get("cisa_kev", False)),
            "active_exploitation": bool(doc.get("active_exploitation", False)),
            "detected_on": parse_dt(doc.get("detected_on"), assume_wib=True)
            or datetime.datetime.now(datetime.UTC),
            "epss_score": doc.get("epss_score"),
            "epss_percentile": doc.get("epss_percentile"),
            "epss_date": doc.get("epss_date"),
            "epss_checked_at": parse_dt(doc.get("epss_checked_at")),
            "cisa_kev_checked_at": parse_dt(doc.get("cisa_kev_checked_at")),
            "cisa_kev_detail": cisa_kev_detail(doc),
            "exploit_db_checked_at": parse_dt(doc.get("exploit_db_checked_at")),
            "exploit_db_hits": doc.get("exploit_db_hits") or [],
            "registered_date": parse_dt(doc.get("registered_date"), assume_wib=True),
        }
        pocs = [
            {"url": p["url"], "source": p.get("source"), "poc_type": p.get("type")}
            for p in doc.get("pocs") or []
            if p.get("url")
        ]
        plan.cves.append(
            Row(
                cve=cve,
                references=[r["url"] for r in doc.get("reference") or [] if r.get("url")],
                affected=flatten_affected(doc.get("affected") or []),
                pocs=pocs,
            )
        )

    for doc in dump.docs("news_db/cve_false_positives"):
        client_id = str(doc.get("client_id") or "default")
        if client_id not in known_clients:
            plan.skipped_no_client.add(client_id)
            continue
        plan.false_positives.append(
            {
                "cve_id": doc["cve_id"],
                "client_id": client_id,
                "marked_by": doc.get("marked_by"),
                "marked_at": parse_dt(doc.get("marked_at"), assume_wib=True)
                or datetime.datetime.now(datetime.UTC),
            }
        )

    tickets_by_pair: dict[tuple[str, str], dict[str, Any]] = {}
    for doc in dump.docs("news_db/cve_tickets"):
        client_id = str(doc.get("client_id") or "default")
        if client_id not in known_clients:
            plan.skipped_no_client.add(client_id)
            continue
        row = {
            "cve_id": doc["cve_id"],
            "client_id": client_id,
            "ticket_id": doc["ticket_id"],
            "affected_asset": doc.get("affected_asset") or None,
            "affected_version": doc.get("affected_version") or None,
            "fixed_version": doc.get("fixed_version") or None,
            "asset_owner": doc.get("asset_owner") or None,
            "owner_email": doc.get("owner_email") or None,
            "owner_team": doc.get("owner_team") or None,
            "active_exploitation": doc.get("active_exploitation") or None,
            "remediation_date_plan": parse_date(doc.get("remediation_date_plan")),
            "remediation_status": doc.get("remediation_status") or None,
            "actual_remediation_date": parse_date(doc.get("actual_remediation_date")),
            "escalation_required": bool(doc.get("escalation_required", False)),
            "comments": doc.get("comments") or None,
            "risk_acceptance": doc.get("risk_acceptance") or None,
            "closure_date": parse_date(doc.get("closure_date")),
            "acknowledged_by": doc.get("acknowledged_by") or None,
            "acknowledge_time": parse_dt(doc.get("acknowledge_time"), assume_wib=True),
        }
        pair = (row["cve_id"], client_id)
        existing = tickets_by_pair.get(pair)
        if existing is None:
            tickets_by_pair[pair] = row
        else:
            plan.duplicate_tickets_dropped += 1
            current = existing["acknowledge_time"] or datetime.datetime.min.replace(
                tzinfo=datetime.UTC
            )
            new = row["acknowledge_time"] or datetime.datetime.min.replace(tzinfo=datetime.UTC)
            if new >= current:
                tickets_by_pair[pair] = row
    plan.tickets = list(tickets_by_pair.values())
    return plan


# --- penulisan -------------------------------------------------------------------------------


def write_plan(session: Session, plan: Plan) -> dict[str, int]:
    cve_new = 0
    ref_new = 0
    aff_new = 0
    poc_new = 0
    for row in plan.cves:
        stmt = (
            pg_insert(CveTracker)
            .values(**row.cve)
            .on_conflict_do_nothing(index_elements=["cve_id", "client_id"])
            .returning(CveTracker.id)
        )
        tracker_id = session.execute(stmt).scalar_one_or_none()
        if tracker_id is None:
            continue  # sudah ada (mis. new_cve sudah jalan buat CVE ini) -- gak nimpa
        cve_new += 1
        if row.references:
            session.execute(
                pg_insert(CveReference).values(
                    [{"cve_tracker_id": tracker_id, "url": u} for u in row.references]
                )
            )
            ref_new += len(row.references)
        if row.affected:
            session.execute(
                pg_insert(CveAffected).values(
                    [{"cve_tracker_id": tracker_id, "affected": a} for a in row.affected]
                )
            )
            aff_new += len(row.affected)
        if row.pocs:
            session.execute(
                pg_insert(CvePoc).values([{"cve_tracker_id": tracker_id, **p} for p in row.pocs])
            )
            poc_new += len(row.pocs)

    fp_new = 0
    if plan.false_positives:
        stmt = (
            pg_insert(CveFalsePositive)
            .values(plan.false_positives)
            .on_conflict_do_nothing(index_elements=["cve_id", "client_id"])
            .returning(CveFalsePositive.id)
        )
        fp_new = len(session.execute(stmt).all())

    ticket_new = 0
    if plan.tickets:
        stmt = (
            pg_insert(CveTicket)
            .values(plan.tickets)
            .on_conflict_do_nothing(index_elements=["cve_id", "client_id"])
            .returning(CveTicket.id)
        )
        ticket_new = len(session.execute(stmt).all())

    return {
        "cve_tracker": cve_new,
        "cve_references": ref_new,
        "cve_affected": aff_new,
        "cve_pocs": poc_new,
        "cve_false_positives": fp_new,
        "cve_tickets": ticket_new,
    }


# --- CLI --------------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("--dump-dir", type=Path, default=DEFAULT_DUMP_DIR)
    ap.add_argument(
        "--dry-run", action="store_true", help="hitung + tampilkan rencana, tanpa nulis"
    )
    args = ap.parse_args(argv)

    with sync_session() as session:
        known_clients = {c for c in session.execute(select(Client.client_id)).scalars().all()}
        if not known_clients:
            print(
                "GAGAL: tabel `clients` kosong -- jalankan `fase10_reference_data.py` dulu",
                file=sys.stderr,
            )
            return 1
        try:
            plan = build_plan(DirDump(args.dump_dir), known_clients)
        except DumpError as e:
            print(f"GAGAL: {e}", file=sys.stderr)
            return 1

        if args.dry_run:
            counts = {
                "cve_tracker": len(plan.cves),
                "cve_references": sum(len(r.references) for r in plan.cves),
                "cve_affected": sum(len(r.affected) for r in plan.cves),
                "cve_pocs": sum(len(r.pocs) for r in plan.cves),
                "cve_false_positives": len(plan.false_positives),
                "cve_tickets": len(plan.tickets),
            }
        else:
            counts = write_plan(session, plan)
            session.commit()

    mode = "DRY-RUN (tidak ditulis)" if args.dry_run else "DITULIS"
    print(f"== migrasi CVE tracker -- {mode} -- dump: {args.dump_dir}")
    for name, n in counts.items():
        print(f"  {name:22} {n:>6}")
    if plan.duplicate_tickets_dropped:
        print(
            f"\n  {plan.duplicate_tickets_dropped} dokumen tiket duplikat (cve_id+client_id sama) "
            "-- yang acknowledge_time-nya paling baru dipakai, sisanya dibuang"
        )
    if plan.skipped_no_client:
        print(f"\n  DILEWATI, client_id tidak ada di `clients`: {sorted(plan.skipped_no_client)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
