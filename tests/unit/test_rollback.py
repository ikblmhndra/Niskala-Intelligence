"""`tools/ops/rollback.py` -- rollback versi platform (Fase 10.G).

Bahaya nyata yang dikunci (ketemu di latihan staging): `CTI_TAG=<lama> docker compose up -d`
dengan DB di revisi yang lebih baru dari image lama = `migrate` gagal DAN api/worker yang sedang
jalan ikut terhenti. Alat ini harus memeriksa dulu, downgrade dengan image SEKARANG, dan tidak
pernah lanjut `up` kalau ada langkah sebelumnya yang gagal.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from tools.ops import rollback as rb

HISTORY = """\
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
a10e5c0de001 -> a10e5c0de002 (head), fase 10.E: scraper_config.options
71dc81d1e99c -> a10e5c0de001, fase 10.E: tabel cve_mentions
cb4d50d510ea -> 71dc81d1e99c, fase 9
<base> -> cb4d50d510ea, skema awal
"""
HISTORY_OLD = """\
71dc81d1e99c -> a10e5c0de001 (head), fase 10.E: tabel cve_mentions
cb4d50d510ea -> 71dc81d1e99c, fase 9
<base> -> cb4d50d510ea, skema awal
"""  # image LAMA: tidak kenal a10e5c0de002
CFG = rb.Config(
    current_tag="new",
    tag="old",
    compose=("docker", "compose", "-p", "x"),
    env_file="stg.env",
    network="net",
    services=("api", "worker"),
    api_url="http://api/healthz",
    wait_s=10,
)


class FakeShell(rb.Shell):
    """Skrip: revisi DB, head tiap image, riwayat; mencatat perintah dan env-nya."""

    def __init__(self, db="a10e5c0de002", heads=None, histories=None) -> None:
        self.db = db
        self.heads = heads or {"old": "a10e5c0de001", "new": "a10e5c0de002"}
        self.histories = histories or {"new": HISTORY, "old": HISTORY_OLD}
        self.calls: list[tuple[list[str], dict[str, str] | None]] = []
        self.fail: str | None = None  # potongan perintah yang dibuat gagal
        self.api_after = 2  # jumlah cek sebelum API "melayani"
        self.checks = 0
        self.clock = 0.0

    def run(self, cmd: Sequence[str], env=None):
        cmd = list(cmd)
        self.calls.append((cmd, env))
        self.clock += 1
        joined = " ".join(cmd)
        if self.fail and self.fail in joined:
            return 1, "kaboom"
        if cmd[:2] == ["docker", "run"]:
            image = next(a for a in cmd if a.startswith("cti-api:")).split(":")[1]
            action = cmd[cmd.index(f"cti-api:{image}") + 1]
            if action == "current":
                return 0, f"INFO  [alembic.runtime.migration] Context\n{self.db} (head)\n"
            if action == "heads":
                return 0, f"{self.heads[image]} (head)\n"
            if action == "history":
                return 0, self.histories[image]
            if action == "downgrade":
                self.db = cmd[-1]
                return 0, "INFO Running downgrade"
        if "up" in cmd:  # service `migrate` menaikkan DB ke head image target
            tag = (env or {}).get("CTI_TAG")
            if tag:
                self.db = self.heads[tag]
            return 0, ""
        raise AssertionError(cmd)

    def http_ok(self, url: str) -> bool:
        self.checks += 1
        return self.checks > self.api_after

    def now(self) -> float:
        return self.clock

    def sleep(self, seconds: float) -> None:
        self.clock += seconds

    def actions(self) -> list[str]:
        out = []
        for cmd, _ in self.calls:
            if cmd[:2] == ["docker", "run"]:
                image = next(a for a in cmd if a.startswith("cti-api:"))
                out.append(f"{cmd[cmd.index(image) + 1]}@{image.split(':')[1]}")
            else:
                out.append("up")
        return out


def quiet(_msg: str) -> None:
    return None


# --- parsing & keputusan -------------------------------------------------------------------------


def test_revision_parsing_skips_log_lines_and_handles_an_empty_database() -> None:
    assert (
        rb.parse_revision("INFO  [alembic] ctx\nWARNI x\na10e5c0de002 (head)\n") == "a10e5c0de002"
    )
    assert rb.parse_revision("INFO  [alembic] Context impl\n") is None
    assert rb.parse_revision("") is None


def test_history_parses_into_a_parent_map_and_ancestors_walk_it() -> None:
    parents = rb.parse_parents(HISTORY)

    assert parents["a10e5c0de002"] == "a10e5c0de001" and parents["cb4d50d510ea"] is None
    assert rb.ancestors("a10e5c0de002", parents) == [
        "a10e5c0de002", "a10e5c0de001", "71dc81d1e99c", "cb4d50d510ea",
    ]  # fmt: skip


@pytest.mark.parametrize(
    "history",
    [
        "a -> bbbbbb (head), x\nc -> bbbbbb (branchpoint), y\n",
        "(aaaaaa, bbbbbb) -> cccccc (mergepoint), merge\n",
        "aaaaaa, bbbbbb -> cccccc, merge\n",
    ],
)
def test_a_non_linear_history_is_refused(history: str) -> None:
    with pytest.raises(rb.RollbackError, match="tidak linear"):
        rb.parse_parents(history)


def test_downgrade_is_needed_only_when_the_database_is_newer_than_the_target() -> None:
    parents = rb.parse_parents(HISTORY)
    newer = rb.decide("a10e5c0de002", "a10e5c0de001", parents)
    assert (newer.downgrade_to, newer.steps) == ("a10e5c0de001", ("a10e5c0de002",))

    two_back = rb.decide("a10e5c0de002", "71dc81d1e99c", parents)
    assert two_back.steps == ("a10e5c0de002", "a10e5c0de001")

    assert rb.decide("a10e5c0de001", "a10e5c0de001", parents).downgrade_to is None  # sama
    assert (
        rb.decide("a10e5c0de001", "a10e5c0de002", parents).downgrade_to is None
    )  # target lebih baru
    assert rb.decide(None, "a10e5c0de001", parents).downgrade_to is None  # DB kosong


def test_histories_of_both_images_are_merged_since_the_old_one_lacks_new_revisions() -> None:
    merged = rb.merge_parents(rb.parse_parents(HISTORY_OLD), rb.parse_parents(HISTORY))

    assert merged["a10e5c0de002"] == "a10e5c0de001"
    # tanpa penggabungan, riwayat image lama saja tak memuat head target -> salah dikira "bercabang"
    with pytest.raises(rb.RollbackError, match="bercabang"):
        rb.decide("a10e5c0de001", "a10e5c0de002", rb.parse_parents(HISTORY_OLD))
    assert rb.decide("a10e5c0de001", "a10e5c0de002", merged).downgrade_to is None


def test_the_same_revision_with_different_parents_across_images_is_refused() -> None:
    other = rb.parse_parents(
        "ffffffffffff -> a10e5c0de001 (head), lain\n<base> -> ffffffffffff, x\n"
    )

    with pytest.raises(rb.RollbackError, match="induk berbeda"):
        rb.merge_parents(rb.parse_parents(HISTORY), other)


def test_an_unreadable_history_line_is_refused_instead_of_skipped() -> None:
    with pytest.raises(rb.RollbackError, match="tak terbaca"):
        rb.parse_parents("a10e5c0de001 -> ??? (head), rusak\n")


def test_diverged_revisions_are_refused_rather_than_guessed() -> None:
    with pytest.raises(rb.RollbackError, match="bercabang"):
        rb.decide("a10e5c0de002", "ffffffffffff", rb.parse_parents(HISTORY))


# --- alur rollback --------------------------------------------------


def test_a_newer_database_is_downgraded_with_the_CURRENT_image_before_switching_tags() -> None:
    sh = FakeShell()

    rb.rollback(CFG, sh, yes=True, log=quiet)

    assert sh.actions() == [
        "current@new", "heads@old", "history@new", "history@old",
        "downgrade@new", "up", "current@old",
    ]  # fmt: skip
    downgrade = next(c for c, _ in sh.calls if c[-2:] == ["downgrade", "a10e5c0de001"])
    assert "cti-api:new" in downgrade  # image LAMA tidak kenal revisi baru -> harus image sekarang
    up_cmd, up_env = sh.calls[-2]
    assert up_cmd == ["docker", "compose", "-p", "x", "up", "-d", "api", "worker"]
    assert up_env == {"CTI_TAG": "old"}


def test_rolling_forward_to_a_newer_image_needs_no_downgrade_and_no_confirmation() -> None:
    """Kasus yang lolos dari versi pertama alat ini: image SEKARANG (lama) tak kenal head target."""
    cfg = rb.Config(**{**CFG.__dict__, "current_tag": "old", "tag": "new"})
    sh = FakeShell(db="a10e5c0de001")

    rb.rollback(cfg, sh, log=quiet)  # tanpa --yes

    assert sh.actions() == [
        "current@old", "heads@new", "history@old", "history@new", "up", "current@new",
    ]  # fmt: skip


def test_without_yes_nothing_is_changed_when_a_downgrade_is_required() -> None:
    sh = FakeShell()

    with pytest.raises(rb.RollbackError, match="--yes"):
        rb.rollback(CFG, sh, log=quiet)

    assert sh.actions() == ["current@new", "heads@old", "history@new", "history@old"]  # hanya baca


def test_no_downgrade_no_confirmation_when_the_schema_already_matches() -> None:
    sh = FakeShell(db="a10e5c0de001")

    rb.rollback(CFG, sh, log=quiet)  # tanpa --yes

    assert "downgrade@new" not in sh.actions() and "up" in sh.actions()


def test_a_failed_downgrade_never_proceeds_to_up() -> None:
    sh = FakeShell()
    sh.fail = "downgrade"

    with pytest.raises(rb.RollbackError, match="downgrade GAGAL"):
        rb.rollback(CFG, sh, yes=True, log=quiet)

    assert "up" not in sh.actions()


def test_a_failed_compose_up_is_reported() -> None:
    sh = FakeShell(db="a10e5c0de001")
    sh.fail = "compose"

    with pytest.raises(rb.RollbackError, match=r"compose up. gagal"):
        rb.rollback(CFG, sh, log=quiet)


def test_dry_run_prints_the_plan_and_executes_nothing_that_changes_state() -> None:
    sh = FakeShell()
    lines: list[str] = []

    rb.rollback(CFG, sh, dry_run=True, log=lines.append)

    assert sh.actions() == ["current@new", "heads@old", "history@new", "history@old"]
    text = "\n".join(lines)
    assert "[dry-run]" in text and "downgrade a10e5c0de001" in text and "CTI_TAG=old" in text


def test_the_api_must_serve_before_rollback_is_declared_done() -> None:
    sh = FakeShell(db="a10e5c0de001")
    sh.api_after = 10**6  # tak pernah melayani

    with pytest.raises(rb.RollbackError, match="API tidak melayani"):
        rb.rollback(CFG, sh, log=quiet)


def test_the_final_database_revision_is_verified() -> None:
    class Drift(FakeShell):
        def run(self, cmd, env=None):
            rc, out = super().run(cmd, env)
            if cmd[:2] == ["docker", "run"] and cmd[-1] == "current" and "up" in self.actions():
                return 0, "a10e5c0de002 (head)\n"  # revisi akhir tak sesuai target
            return rc, out

    with pytest.raises(rb.RollbackError, match="revisi DB akhir"):
        rb.rollback(CFG, Drift(), yes=True, log=quiet)


def test_failures_in_the_preflight_reads_abort_before_any_change() -> None:
    """Tiap bacaan pre-flight yang gagal berhenti DENGAN PESANNYA SENDIRI (bukan tertangkap oleh
    pemeriksaan lain di hilir dengan alasan yang salah)."""
    for broken in ("current", "heads", "history"):
        sh = FakeShell()
        sh.fail = broken

        with pytest.raises(rb.RollbackError, match=f"alembic {broken}. gagal"):
            rb.rollback(CFG, sh, yes=True, log=quiet)

        assert "up" not in sh.actions() and not any(a.startswith("downgrade") for a in sh.actions())


def test_cli_exit_codes_and_argument_wiring(capsys) -> None:
    sh = FakeShell()
    argv = ["--current-tag", "new", "--tag", "old", "--env-file", "e.env", "--network", "net",
            "--compose", "docker compose -p x", "--services", "api"]  # fmt: skip

    assert rb.main([*argv, "--yes"], shell=sh) == 0
    assert "SELESAI: tag=old" in capsys.readouterr().out
    assert rb.main(argv, shell=FakeShell()) == 1  # tanpa --yes
    assert "GAGAL" in capsys.readouterr().err
