"""Seed 3 tabel referensi Fase 5 dari dump Mongo arsip (`legacy/dump/`) --
`threat_actor_groups`, `monitored_people`, `ioc_allowlist_entries`. Ketiganya
kosong sejak tabelnya dibikin (lihat `db/models/threat_reference.py`/
`ioc_reference.py`) karena data kuratif aslinya cuma ada di Mongo, bukan
sesuatu yang bisa disintesis.

BUKAN bagian dari `tools/seed` versi Fase 10 (`techstack`/`monitored_accounts`/
`users`/`roles`/`clients`, lihat plan §"Verifikasi end-to-end") -- itu scope
lebih luas, dikerjain nanti pas cutover beneran. Script ini spesifik nutup
gap Fase 5 (`mentioned_group`/`mentioned_apac_people` di `score.py` selalu
kosong tanpa ini) dan `ioc_allowlist` (dipakai `extract_iocs` stage).

Sumber:
  - `legacy/dump/threatintel/groups.bson`       -> ThreatActorGroup (3991 baris, malpedia)
  - `legacy/dump/threatintel/apac-people.bson`   -> MonitoredPerson (30 baris --
                                                     demonym/nasionalitas, BUKAN nama orang,
                                                     walau nama koleksinya "apac-people")
  - `legacy/dump/news_db/ioc_allowlist.bson`     -> IocAllowlistEntry (9 baris)

Idempoten -- boleh dijalankan berkali-kali, upsert by unique constraint
(`name`/`type+value`), gak bakal dobel kalau di-run ulang.

Jalanin (BUTUH `pymongo` buat baca BSON -- SENGAJA gak masuk dependency
package manapun, ini script sekali pakai/migrasi, bukan kode aplikasi):

    uv run --with pymongo python tools/seed/fase5_reference_data.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages/cti-core/src"))

import bson
from cti_core.db.engine import sync_session
from cti_core.db.models.ioc_reference import IocAllowlistEntry
from cti_core.db.models.threat_reference import MonitoredPerson, ThreatActorGroup
from sqlalchemy import select
from sqlalchemy.orm import Session

DUMP_ROOT = Path(__file__).resolve().parents[2] / "legacy" / "dump"
GROUPS_BSON = DUMP_ROOT / "threatintel" / "groups.bson"
APAC_PEOPLE_BSON = DUMP_ROOT / "threatintel" / "apac-people.bson"
IOC_ALLOWLIST_BSON = DUMP_ROOT / "news_db" / "ioc_allowlist.bson"


def _decode(path: Path) -> list[dict]:
    return bson.decode_all(path.read_bytes())


def seed_threat_actor_groups(session: Session) -> tuple[int, int]:
    docs = _decode(GROUPS_BSON)
    existing = set(session.execute(select(ThreatActorGroup.name)).scalars().all())
    inserted = 0
    for doc in docs:
        name = (doc.get("name") or "").strip()
        if not name or name in existing:
            continue
        session.add(ThreatActorGroup(name=name))
        existing.add(name)
        inserted += 1
    session.flush()
    return inserted, len(docs)


def seed_monitored_people(session: Session) -> tuple[int, int]:
    docs = _decode(APAC_PEOPLE_BSON)
    existing = set(session.execute(select(MonitoredPerson.name)).scalars().all())
    inserted = 0
    for doc in docs:
        name = (doc.get("name") or "").strip()
        if not name or name in existing:
            continue
        session.add(MonitoredPerson(name=name))
        existing.add(name)
        inserted += 1
    session.flush()
    return inserted, len(docs)


def seed_ioc_allowlist(session: Session) -> tuple[int, int]:
    docs = _decode(IOC_ALLOWLIST_BSON)
    existing = set(
        session.execute(select(IocAllowlistEntry.type, IocAllowlistEntry.value)).all()
    )
    inserted = 0
    for doc in docs:
        type_ = (doc.get("type") or "").strip()
        value = (doc.get("value") or "").strip()
        if not type_ or not value or (type_, value) in existing:
            continue
        session.add(IocAllowlistEntry(type=type_, value=value))
        existing.add((type_, value))
        inserted += 1
    session.flush()
    return inserted, len(docs)


def main() -> None:
    with sync_session() as session:
        g_new, g_total = seed_threat_actor_groups(session)
        p_new, p_total = seed_monitored_people(session)
        a_new, a_total = seed_ioc_allowlist(session)
        session.commit()

    print(f"threat_actor_groups : {g_new} baru / {g_total} di dump")
    print(f"monitored_people    : {p_new} baru / {p_total} di dump")
    print(f"ioc_allowlist       : {a_new} baru / {a_total} di dump")


if __name__ == "__main__":
    main()
