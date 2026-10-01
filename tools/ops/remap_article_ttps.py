#!/usr/bin/env python3
"""Remap TTP artikel yang SUDAH tersimpan ke katalog ATT&CK (QA 2026-10-01, BUG-C01/BUG-04/BUG-B8).

Enrichment baru sudah menormalisasi TTP (`cti_core.attack_ttp`), tapi baris `article_ttps` lama
masih berisi pasangan ID/nama mentah LLM (T1548 "Privilege Escalation", T1110 "Credential
Dumping", dst). Script ini menjalankan aturan normalisasi yang sama ke semua artikel:

  - nama dikenali katalog -> ID ikut katalog ("Credential Dumping" T1110 -> T1003)
  - nama tactic -> baris dibuang
  - nama karangan + ID valid -> nama diganti nama kanonik
  - teks asli LLM disimpan di `extracted_id`/`extracted_name`

Prasyarat: migrasi `c3a7e9d1f2b4` sudah jalan DAN sync ATT&CK sudah jalan SESUDAH migrasi itu
(sync mengisi `attack_technique_aliases` -- technique revoked). Katalog kosong -> ditolak (exit 1).
Idempoten, aman diulang (mis. sesudah sync ATT&CK versi baru). `--dry-run` = hitung + contoh
perubahan, lalu ROLLBACK.

Dari host (dev):
    uv run python tools/ops/remap_article_ttps.py --dry-run
    uv run python tools/ops/remap_article_ttps.py

Di server (image worker tidak membawa `tools/`, di-mount read-only seperti runbook 3.2):
    docker run --rm --network <project>_default --env-file .env -v "$PWD/tools:/tools:ro" \\
      --entrypoint python cti-worker:$CTI_TAG /tools/ops/remap_article_ttps.py --dry-run
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="hitung perubahan lalu rollback")
    ap.add_argument("--batch-size", type=int, default=500)
    args = ap.parse_args(argv)

    from cti_core.db.engine import get_sync_engine
    from cti_core.db.repositories.ttp_catalog import load_catalog, remap_article_ttps
    from sqlalchemy.orm import Session

    with Session(get_sync_engine()) as session:
        catalog = load_catalog(session)
        try:
            stats = remap_article_ttps(session, catalog, batch_size=args.batch_size)
        except ValueError as e:
            print(f"DITOLAK: {e}", file=sys.stderr)
            return 1
        for line in stats.examples:
            print(line)
        print(
            f"katalog: {len(catalog.names)} technique, {len(catalog.revoked_ids)} revoked | "
            f"artikel: {stats.articles_scanned} dipindai, {stats.articles_changed} berubah | "
            f"baris article_ttps: {stats.rows_before} -> {stats.rows_after}"
        )
        if args.dry_run:
            session.rollback()
            print("DRY RUN -- tidak ada yang ditulis.")
        else:
            session.commit()
            print("Selesai, sudah di-commit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
