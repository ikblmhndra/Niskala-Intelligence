"""Seed 3 tabel referensi Fase 5 dari dump Mongo arsip (`legacy/dump/`) --
`threat_actor_groups`, `monitored_people`, `ioc_allowlist_entries`.

**Sudah digabung ke `fase10_reference_data.py`** (langkah 6 runbook cutover).
Script ini dipertahankan cuma sebagai jalan pintas yang ngisi TIGA tabel itu
saja, dan sekarang memakai fungsi seed yang SAMA -- dulu implementasinya
terpisah, ngebuang kolom `source`/`added_date` grup TA, path dump-nya
di-hardcode, dan gak pernah masuk runbook. Akibatnya staging yang dibangun
dari nol gak punya `threat_actor_groups` sama sekali dan `stages/score.py`
gak pernah nemu threat actor (QA 2026-10-01: 0 dari 325 artikel).

Sumber:
  - `threatintel/groups.bson`       -> ThreatActorGroup (3991 baris)
  - `threatintel/apac-people.bson`  -> MonitoredPerson (30 baris -- demonym/
                                       nasionalitas, BUKAN nama orang)
  - `news_db/ioc_allowlist.bson`    -> IocAllowlistEntry (9 baris)

Idempoten. Jalankan (butuh `pymongo` buat baca BSON):

    uv run --with pymongo python tools/seed/fase5_reference_data.py [--dump-dir DIR] [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cti_core.db.engine import sync_session

if __package__ in (None, ""):  # dijalankan sebagai skrip: `python tools/seed/...`
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.seed._dump import DEFAULT_DUMP_DIR, DirDump, DumpError
from tools.seed.fase10_reference_data import (
    seed_ioc_allowlist,
    seed_monitored_people,
    seed_threat_actor_groups,
)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("--dump-dir", type=Path, default=DEFAULT_DUMP_DIR)
    ap.add_argument("--dry-run", action="store_true", help="jalankan semua lalu rollback")
    args = ap.parse_args(argv)

    dump = DirDump(args.dump_dir)
    try:
        with sync_session() as session:
            results = {
                "threat_actor_groups": seed_threat_actor_groups(
                    session, dump.docs("threatintel/groups")
                ),
                "monitored_people": seed_monitored_people(
                    session, dump.docs("threatintel/apac-people")
                ),
                "ioc_allowlist_entries": seed_ioc_allowlist(
                    session, dump.docs("news_db/ioc_allowlist")
                ),
            }
            if args.dry_run:
                session.rollback()
    except DumpError as e:
        print(f"GAGAL, tidak ada yang ditulis: {e}", file=sys.stderr)
        return 1

    mode = "DRY-RUN (di-rollback)" if args.dry_run else "DITULIS"
    print(f"== seed referensi threat/IOC -- {mode} -- dump: {args.dump_dir}")
    for name, tally in results.items():
        print(f"{name:22}: {tally.inserted} baru / {tally.existing} sudah ada")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
