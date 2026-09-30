"""`tools/ops/rundeck_schedule.py` -- matikan/nyalakan lagi jadwal Rundeck lama (Fase 10.G).
API Rundeck palsu; yang dikunci: hanya job yang MEMANG aktif yang disentuh, rollback menyalakan
persis himpunan yang sama, dan token salah menghentikan semuanya sejak panggilan pertama."""

from __future__ import annotations

import json
import stat
import threading
from pathlib import Path

import pytest

from tools.ops import rundeck_schedule as rs

TOKEN = "rd-SECRET-TOKEN-0123456789"
URL = "http://rundeck.test:4440"

LISTING = [
    {"id": "j1", "name": "aktif-1", "scheduled": True, "scheduleEnabled": True, "enabled": True},
    {
        "id": "j2",
        "name": "aktif-2",
        "scheduled": True,
        "scheduleEnabled": True,
    },  # `enabled` absen = aktif
    {
        "id": "j3",
        "name": "jadwal-mati",
        "scheduled": True,
        "scheduleEnabled": False,
        "enabled": True,
    },
    {
        "id": "j4",
        "name": "tanpa-jadwal",
        "scheduled": False,
        "scheduleEnabled": False,
        "enabled": True,
    },
    {
        "id": "j5",
        "name": "eksekusi-mati",
        "scheduled": True,
        "scheduleEnabled": True,
        "enabled": False,
    },
]


class FakeRundeck:
    def __init__(self, listing=LISTING) -> None:
        self.listing = [dict(j) for j in listing]
        self.calls: list[tuple[str, str]] = []
        self.headers: list[dict[str, str]] = []
        self.status_for: dict[str, list[int]] = {}
        self.token_ok = True
        self.lock = threading.Lock()

    def __call__(self, method: str, url: str, headers: dict[str, str]):
        with self.lock:
            self.calls.append((method, url.removeprefix(URL + "/api/48")))
            self.headers.append(headers)
        if not self.token_ok or headers.get("X-Rundeck-Auth-Token") != TOKEN:
            return 401, b"{}"
        path = url.removeprefix(URL + "/api/48")
        if path.endswith("/jobs"):
            return 200, json.dumps(self.listing).encode()
        job_id = path.split("/")[2]
        queue = self.status_for.get(job_id)
        if queue:
            return queue.pop(0), b"{}"
        enable = path.endswith("/schedule/enable")
        for j in self.listing:
            if j["id"] == job_id:
                j["scheduleEnabled"] = enable
        return 200, b'{"success":true}'

    def posts(self) -> list[str]:
        return sorted(p for m, p in self.calls if m == "POST")


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RD_URL", URL)
    monkeypatch.setenv("RD_PROJECT", "Threat-Information")
    monkeypatch.setenv("RD_TOKEN", TOKEN)
    monkeypatch.setattr(rs.time, "sleep", lambda s: None)


def run(argv: list[str], fake: FakeRundeck) -> int:
    return rs.main(argv, http=fake)


def snapshot(tmp_path: Path, fake: FakeRundeck) -> Path:
    path = tmp_path / "snap.json"
    assert run(["snapshot", "--out", str(path)], fake) == 0
    return path


# --- snapshot ----------------------------------------------------------------------------------


def test_snapshot_records_only_jobs_that_actually_fire_and_is_private(
    tmp_path: Path, capsys
) -> None:
    fake = FakeRundeck()

    path = snapshot(tmp_path, fake)

    data = json.loads(path.read_text())
    assert [j["id"] for j in data["active_jobs"]] == ["j1", "j2"]
    assert data["total"] == 5 and data["project"] == "Threat-Information"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert "2 job aktif dari 5" in capsys.readouterr().out
    assert fake.posts() == []  # snapshot tidak mengubah apa pun


# --- disable / enable -----------------------------------------------------------------------------


def test_disable_touches_only_the_snapshotted_active_jobs(tmp_path: Path, capsys) -> None:
    fake = FakeRundeck()
    snap = snapshot(tmp_path, fake)

    assert run(["disable", "--snapshot", str(snap)], fake) == 0

    assert fake.posts() == ["/job/j1/schedule/disable", "/job/j2/schedule/disable"]
    assert "2/2 job dimatikan" in capsys.readouterr().out


def test_rollback_re_enables_exactly_the_jobs_that_were_active_before(tmp_path: Path) -> None:
    """Job yang memang sengaja mati (j3-j5) TIDAK ikut menyala saat rollback."""
    fake = FakeRundeck()
    snap = snapshot(tmp_path, fake)
    run(["disable", "--snapshot", str(snap)], fake)
    fake.calls.clear()

    assert run(["enable", "--snapshot", str(snap)], fake) == 0

    assert fake.posts() == ["/job/j1/schedule/enable", "/job/j2/schedule/enable"]
    assert {j["id"]: j["scheduleEnabled"] for j in fake.listing}["j3"] is False


def test_the_snapshot_not_the_live_state_decides_so_a_second_disable_is_harmless(
    tmp_path: Path,
) -> None:
    fake = FakeRundeck()
    snap = snapshot(tmp_path, fake)

    assert run(["disable", "--snapshot", str(snap)], fake) == 0
    assert run(["disable", "--snapshot", str(snap)], fake) == 0
    assert run(["enable", "--snapshot", str(snap)], fake) == 0


def test_dry_run_prints_the_plan_and_changes_nothing(tmp_path: Path, capsys) -> None:
    fake = FakeRundeck()
    snap = snapshot(tmp_path, fake)

    assert run(["disable", "--snapshot", str(snap), "--dry-run"], fake) == 0

    assert fake.posts() == []
    assert "[dry-run] disable j1" in capsys.readouterr().out


def test_status_counts_the_snapshotted_jobs_that_still_fire(tmp_path: Path, capsys) -> None:
    fake = FakeRundeck()
    snap = snapshot(tmp_path, fake)
    capsys.readouterr()

    run(["status", "--snapshot", str(snap)], fake)
    assert "2/2 job dari snapshot SEDANG menembak" in capsys.readouterr().out

    run(["disable", "--snapshot", str(snap)], fake)
    capsys.readouterr()
    run(["status", "--snapshot", str(snap)], fake)
    assert "0/2 job dari snapshot SEDANG menembak" in capsys.readouterr().out


# --- kegagalan ------------------------------------------------------------


def test_a_transient_failure_is_retried_and_a_persistent_one_is_reported_with_exit_1(
    tmp_path: Path, capsys
) -> None:
    fake = FakeRundeck()
    snap = snapshot(tmp_path, fake)
    fake.status_for = {
        "j1": [503, 0],
        "j2": [500, 500, 500],
    }  # j1 pulih di percobaan ke-3; j2 tidak

    rc = run(["disable", "--snapshot", str(snap)], fake)

    assert rc == 1
    captured = capsys.readouterr()
    assert "1/2 job dimatikan" in captured.out and "GAGAL: j2 (aktif-2)" in captured.err
    assert "GAGAL: j1" not in captured.err


def test_one_failing_job_does_not_stop_the_others(tmp_path: Path) -> None:
    fake = FakeRundeck()
    snap = snapshot(tmp_path, fake)
    fake.status_for = {"j1": [404]}  # job sudah dihapus di Rundeck

    assert run(["disable", "--snapshot", str(snap)], fake) == 1
    assert {j["id"]: j["scheduleEnabled"] for j in fake.listing}["j2"] is False


def test_a_rejected_token_aborts_on_the_first_call_instead_of_failing_every_job(
    tmp_path: Path, capsys
) -> None:
    fake = FakeRundeck()
    snap = snapshot(tmp_path, fake)
    fake.token_ok = False
    fake.calls.clear()

    rc = run(["disable", "--snapshot", str(snap)], fake)

    assert rc == 1 and "menolak token" in capsys.readouterr().err
    assert (
        len(fake.calls) <= rs.WORKERS
    )  # tiap worker paling banyak satu panggilan, bukan retry x job


def test_missing_environment_fails_before_any_network_call(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("RD_TOKEN")
    fake = FakeRundeck()

    assert run(["snapshot", "--out", str(tmp_path / "x.json")], fake) == 1
    assert fake.calls == []


def test_the_token_is_never_printed(tmp_path: Path, capsys) -> None:
    fake = FakeRundeck()
    snap = snapshot(tmp_path, fake)
    fake.status_for = {"j1": [500, 500, 500]}

    run(["disable", "--snapshot", str(snap)], fake)
    run(["status", "--snapshot", str(snap)], fake)

    captured = capsys.readouterr()
    assert TOKEN not in captured.out + captured.err
    assert TOKEN not in snap.read_text()


def test_the_token_travels_only_in_the_header_and_uses_api_v48(tmp_path: Path) -> None:
    fake = FakeRundeck()

    snapshot(tmp_path, fake)

    assert fake.headers[0] == {"X-Rundeck-Auth-Token": TOKEN, "Accept": "application/json"}
    assert fake.calls[0] == ("GET", "/project/Threat-Information/jobs")
