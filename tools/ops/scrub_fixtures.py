#!/usr/bin/env python3
"""Scrub string mirip-secret dari fixture HTTP hasil rekaman, berdasarkan laporan gitleaks.

Fixture (`tests/fixtures/`) adalah salinan halaman/feed PUBLIK pihak ketiga, jadi
"secret" di dalamnya bukan milik kita: key publik front-end (reCAPTCHA sitekey,
BOOMR/mPulse, form id HubSpot), sampel di artikel berita ("ID AWS AKIA... bocor"),
atau JWT konfigurasi halaman. Tetap gak boleh masuk repo apa adanya -- scanner
eksternal (GitHub secret scanning) gak bisa bedain, dan gate `gitleaks` di CI
jadi buta kalau folder ini di-allowlist.

Alur setelah merekam fixture baru (`tools/salvage/record_fixtures.py` /
`cti-scraper verify --record`):

    docker run --rm -v "$PWD/tests/fixtures:/src:ro" -v /tmp/gl:/out \\
        zricethezav/gitleaks:latest detect --no-git --source /src --no-banner \\
        --report-format json --report-path /out/report.json
    uv run python tools/ops/scrub_fixtures.py /tmp/gl/report.json \\
        --root tests/fixtures --strip-prefix /src

Tiap secret yang dilaporkan diganti string sepanjang SAMA berisi `REDACTED` +
garis bawah -- panjang dijaga biar offset/parse gak geser, dan bukan karakter
yang cocok pola token mana pun, jadi scan ulang bersih. Semua kemunculan secret
di file itu diganti (bukan cuma baris yang dilaporkan). Aman dijalankan ulang:
secret yang sudah diganti gak ketemu lagi.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path


def placeholder(secret: str) -> str:
    """Pengganti sepanjang `secret` (dalam karakter), tanpa huruf/angka acak."""
    return ("REDACTED" + "_" * len(secret))[: len(secret)]


def scrub(
    report: list[dict], *, root: Path, strip_prefix: str = "", dry_run: bool = False
) -> tuple[int, list[str]]:
    """Return (jumlah penggantian, daftar peringatan). Secret dikelompokkan per
    file supaya tiap file dibaca-tulis sekali."""
    by_file: dict[str, set[str]] = defaultdict(set)
    for finding in report:
        name = str(finding["File"])
        if strip_prefix and name.startswith(strip_prefix):
            name = name[len(strip_prefix) :]
        secret = finding.get("Secret") or ""
        if secret:
            by_file[name.lstrip("/")].add(secret)

    replaced = 0
    warnings: list[str] = []
    for rel, secrets in sorted(by_file.items()):
        path = root / rel
        if not path.is_file():
            warnings.append(f"file gak ada, dilewati: {path}")
            continue
        data = path.read_bytes()
        # Yang terpanjang dulu: secret yang jadi substring secret lain gak
        # boleh mengubahnya jadi setengah-terganti duluan.
        for secret in sorted(secrets, key=len, reverse=True):
            raw = secret.encode()
            count = data.count(raw)
            if count:
                data = data.replace(raw, placeholder(secret).encode())
                replaced += count
        if not dry_run:
            path.write_bytes(data)
    return replaced, warnings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("report", type=Path, help="laporan gitleaks (--report-format json)")
    ap.add_argument("--root", type=Path, default=Path("tests/fixtures"))
    ap.add_argument("--strip-prefix", default="", help="mis. /src kalau gitleaks jalan di docker")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    report = json.loads(args.report.read_text())
    replaced, warnings = scrub(
        report, root=args.root, strip_prefix=args.strip_prefix, dry_run=args.dry_run
    )
    for w in warnings:
        print(f"PERINGATAN: {w}", file=sys.stderr)
    verb = "akan diganti" if args.dry_run else "diganti"
    print(f"{len(report)} temuan -> {replaced} kemunculan {verb}")
    return 1 if warnings else 0


if __name__ == "__main__":
    raise SystemExit(main())
