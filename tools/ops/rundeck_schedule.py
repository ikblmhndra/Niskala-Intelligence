#!/usr/bin/env python3
"""Matikan / nyalakan LAGI jadwal job Rundeck lama (Fase 10.G) -- langkah cutover 10.3 dan
rollback "stack lama nyala <5 menit". Cuma stdlib, jalan dari laptop/host mana pun yang
bisa menjangkau Rundeck.

    export RD_URL=http://10.8.20.78:4440 RD_PROJECT=Threat-Information
    export RD_TOKEN=...          # token API Rundeck, JANGAN sebagai argumen

    RS=tools/ops/rundeck_schedule.py; SNAP=rundeck-before-cutover.json
    python3 $RS snapshot --out $SNAP
    python3 $RS disable  --snapshot $SNAP      # cutover
    python3 $RS status   --snapshot $SNAP
    python3 $RS enable   --snapshot $SNAP      # ROLLBACK

Kuncinya `snapshot`: daftar job yang SEDANG AKTIF (terjadwal + jadwal menyala + eksekusi
menyala) direkam SEBELUM cutover. `disable` dan `enable` hanya menyentuh job di daftar itu --
rollback menyalakan persis yang dulu menyala, tidak menyalakan 133 job yang memang sengaja
mati. Ambil snapshot BARU tepat sebelum cutover: `docs/legacy/rundeck-jobs-map.json` itu
rekaman Fase 0 dan bisa sudah basi.

Panggilan dijalankan paralel (8 sekaligus, 2 percobaan ulang untuk 5xx/koneksi). 401/403 =
token salah -> berhenti SEGERA (bukan 100 kegagalan berurutan). Token tidak pernah dicetak
dan tidak pernah masuk pesan error. Exit code 0 = semua berhasil, 1 = ada yang gagal.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

API_VERSION = "48"
WORKERS = 8
RETRIES = 2

Http = Callable[[str, str, dict[str, str]], tuple[int, bytes]]
"""(method, url, headers) -> (status, body). Status 0 = gagal koneksi."""


class RundeckError(Exception):
    """Kegagalan fatal (token ditolak, respons tak terbaca)."""


@dataclass(frozen=True)
class Job:
    id: str
    name: str
    active: bool
    """Terjadwal DAN jadwal menyala DAN eksekusi menyala = benar-benar menembak."""


def urllib_http(method: str, url: str, headers: dict[str, str]) -> tuple[int, bytes]:
    request = urllib.request.Request(
        url, method=method, headers=headers, data=b"" if method == "POST" else None
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except (urllib.error.URLError, OSError):
        return 0, b""


class Rundeck:
    def __init__(self, url: str, token: str, project: str, *, http: Http = urllib_http) -> None:
        self.base = url.rstrip("/") + f"/api/{API_VERSION}"
        self.project = project
        self.http = http
        self._headers = {"X-Rundeck-Auth-Token": token, "Accept": "application/json"}

    def _call(self, method: str, path: str) -> tuple[int, bytes]:
        status, body = 0, b""
        for attempt in range(RETRIES + 1):
            status, body = self.http(method, self.base + path, self._headers)
            if status in (401, 403):
                raise RundeckError(f"Rundeck menolak token (HTTP {status}) -- periksa RD_TOKEN")
            if status != 0 and status < 500:
                return status, body
            if attempt < RETRIES:
                time.sleep(0.2 * (attempt + 1))
        return status, body

    def jobs(self) -> list[Job]:
        status, body = self._call("GET", f"/project/{self.project}/jobs")
        if status != 200:
            raise RundeckError(f"gagal mengambil daftar job (HTTP {status})")
        try:
            raw = json.loads(body)
        except ValueError as e:
            raise RundeckError("daftar job bukan JSON valid") from e
        return [
            Job(
                id=str(j["id"]),
                name=str(j.get("name", "")),
                active=bool(
                    j.get("scheduled") and j.get("scheduleEnabled") and j.get("enabled", True)
                ),
            )
            for j in raw
        ]

    def set_schedule(self, job_id: str, *, enabled: bool) -> bool:
        action = "enable" if enabled else "disable"
        status, _ = self._call("POST", f"/job/{job_id}/schedule/{action}")
        return status == 200


def read_snapshot(path: Path) -> list[Job]:
    return [Job(j["id"], j["name"], True) for j in json.loads(path.read_text())["active_jobs"]]


def write_snapshot(path: Path, jobs: Sequence[Job], project: str) -> None:
    active = [{"id": j.id, "name": j.name} for j in jobs if j.active]
    path.write_text(
        json.dumps({"project": project, "total": len(jobs), "active_jobs": active}, indent=1)
    )
    os.chmod(path, 0o600)


@dataclass(frozen=True)
class BatchResult:
    done: int
    failed: list[str]


def apply(
    client: Rundeck, jobs: Sequence[Job], *, enabled: bool, dry_run: bool = False
) -> BatchResult:
    if dry_run:
        for j in jobs:
            print(f"  [dry-run] {'enable' if enabled else 'disable'} {j.id}  {j.name}")
        return BatchResult(0, [])
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        outcomes = list(pool.map(lambda j: client.set_schedule(j.id, enabled=enabled), jobs))
    failed = [f"{j.id} ({j.name})" for j, ok in zip(jobs, outcomes, strict=True) if not ok]
    return BatchResult(len(jobs) - len(failed), failed)


def main(argv: Sequence[str] | None = None, *, http: Http = urllib_http) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--url", default=os.environ.get("RD_URL", ""))
    parser.add_argument("--project", default=os.environ.get("RD_PROJECT", ""))
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("snapshot")
    p.add_argument("--out", type=Path, required=True)
    for name in ("disable", "enable", "status"):
        p = sub.add_parser(name)
        p.add_argument("--snapshot", type=Path, required=True)
        if name != "status":
            p.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    token = os.environ.get("RD_TOKEN", "")
    if not (args.url and args.project and token):
        print("GAGAL: RD_URL, RD_PROJECT, dan RD_TOKEN (env) wajib terisi", file=sys.stderr)
        return 1
    client = Rundeck(args.url, token, args.project, http=http)
    started = time.monotonic()

    try:
        if args.command == "snapshot":
            jobs = client.jobs()
            write_snapshot(args.out, jobs, args.project)
            active = sum(j.active for j in jobs)
            print(f"OK snapshot: {active} job aktif dari {len(jobs)} -> {args.out}")
            return 0

        targets = read_snapshot(args.snapshot)
        if args.command == "status":
            live = {j.id: j.active for j in client.jobs()}
            firing = [j for j in targets if live.get(j.id)]
            print(f"status: {len(firing)}/{len(targets)} job dari snapshot SEDANG menembak jadwal")
            return 0
        result = apply(client, targets, enabled=args.command == "enable", dry_run=args.dry_run)
    except RundeckError as e:
        print(f"GAGAL: {e}", file=sys.stderr)
        return 1

    verb = "dinyalakan" if args.command == "enable" else "dimatikan"
    if not args.dry_run:
        print(f"{result.done}/{len(targets)} job {verb} dalam {time.monotonic() - started:.1f} dtk")
    for line in result.failed:
        print(f"  GAGAL: {line}", file=sys.stderr)
    return 1 if result.failed else 0


if __name__ == "__main__":
    sys.exit(main())
