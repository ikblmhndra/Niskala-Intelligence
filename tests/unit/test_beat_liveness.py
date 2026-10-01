"""Liveness scheduler (QA BUG-D2/D7/D8, insiden staging 2026-09-26 15:42 -> 09-30 17:17 UTC):

- `cti_core.beat_heartbeat` -- encode/parse/klasifikasi heartbeat (kontrak worker <-> API),
- `cti_worker.scheduler.skip_stale_catchup` -- beat yang nyala lagi sesudah mati lama GAK
  nembak semua entri sekaligus (dulu: 94 scraper + laporan mingguan di hari Rabu),
- `CtiScheduler._maybe_heartbeat` -- nulis heartbeat, gagal Redis gak matiin beat,
- `cti_worker.beat_watchdog.check_once` -- alarm di LUAR beat, dedupe lintas worker,
- `cti_scraper.health.next_run` -- kolom "Next Run".
"""

from __future__ import annotations

import datetime

import pytest
from celery import Celery
from celery.beat import ScheduleEntry
from celery.schedules import crontab
from cti_core import beat_heartbeat
from cti_scraper.health import next_run

UTC = datetime.UTC
NOW = datetime.datetime(2026, 9, 30, 17, 17, 54, tzinfo=UTC)  # beat staging nyala lagi


@pytest.fixture(autouse=True)
def _settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    from cti_core.config import get_settings

    monkeypatch.setenv("DATABASE__URL", "postgresql+asyncpg://x:x@127.0.0.1:1/x")
    monkeypatch.setenv("DATABASE__SYNC_URL", "postgresql+psycopg://x:x@127.0.0.1:1/x")
    monkeypatch.setenv("AUTH__JWT_SECRET", "test")
    monkeypatch.setenv("AUTH__SESSION_SECRET_KEY", "test")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# --- heartbeat ---------------------------------------------------------------


def test_heartbeat_roundtrip_and_classification() -> None:
    started = NOW - datetime.timedelta(hours=1)
    raw = beat_heartbeat.encode(NOW - datetime.timedelta(seconds=30), started)

    hb = beat_heartbeat.parse(raw)
    assert hb is not None and hb.started_at == started

    ok = beat_heartbeat.classify(hb, now=NOW, stale_after_s=300)
    assert ok.state == "ok" and ok.age_s == pytest.approx(30)

    stale = beat_heartbeat.classify(hb, now=NOW + datetime.timedelta(minutes=10), stale_after_s=300)
    assert stale.state == "stale"


@pytest.mark.parametrize("raw", [None, "", "bukan json", "[]", '{"last_tick": "x"}', b"{}"])
def test_missing_or_corrupt_heartbeat_is_unknown_not_an_exception(raw: object) -> None:
    hb = beat_heartbeat.parse(raw)  # type: ignore[arg-type]
    assert hb is None
    assert beat_heartbeat.classify(hb, now=NOW, stale_after_s=300).state == "unknown"


def test_heartbeat_parse_accepts_bytes_from_sync_redis() -> None:
    raw = beat_heartbeat.encode(NOW, None).encode()
    hb = beat_heartbeat.parse(raw)
    assert hb is not None and hb.last_tick == NOW and hb.started_at is None


# --- D7: catch-up basi pas start ------------------------------------------------


def _entry(name: str, cron: crontab, last_run_at: datetime.datetime) -> ScheduleEntry:
    app = Celery()
    app.conf.timezone = "UTC"
    cron.nowfun = lambda: NOW
    return ScheduleEntry(name=name, task="t", schedule=cron, last_run_at=last_run_at, app=app)


def test_stale_entries_are_skipped_recent_slot_is_still_caught_up() -> None:
    from cti_worker.scheduler import skip_stale_catchup

    four_days_ago = datetime.datetime(2026, 9, 26, 15, 42, tzinfo=UTC)
    monday = crontab(minute=0, hour=0, day_of_week=1)
    weekly = _entry("scrape-any_run_trends", monday, four_days_ago)
    # hourly :17 -> slot 17:17:00 baru lewat 54 dtk (restart pas slotnya) -> tetap catch-up
    hourly_recent = _entry("scrape-x", crontab(minute=17), four_days_ago)
    # hourly :47 -> slot terakhir 16:47, 30 mnt lalu (> grace 10 mnt) -> dilompatin
    hourly_old = _entry("scrape-y", crontab(minute=47), four_days_ago)
    # gak due sama sekali (jalan barusan) -> gak disentuh
    fresh_last = NOW - datetime.timedelta(seconds=10)
    fresh = _entry("scrape-z", crontab(minute=17), fresh_last)

    skipped = skip_stale_catchup([weekly, hourly_recent, hourly_old, fresh], now=NOW, grace_s=600)

    assert sorted(skipped) == ["scrape-any_run_trends", "scrape-y"]
    assert weekly.last_run_at == NOW and hourly_old.last_run_at == NOW
    assert weekly.is_due()[0] is False  # mingguan nunggu Senin berikutnya
    assert hourly_recent.is_due()[0] is True
    assert hourly_recent.last_run_at == four_days_ago
    assert fresh.last_run_at == fresh_last


def test_grace_window_is_respected() -> None:
    from cti_worker.scheduler import skip_stale_catchup

    last = datetime.datetime(2026, 9, 30, 15, 0, tzinfo=UTC)
    e = _entry("scrape-y", crontab(minute=47), last)  # slot terakhir 16:47 = 30 mnt 54 dtk lalu

    assert skip_stale_catchup([e], now=NOW, grace_s=3600) == []  # jendela 1 jam: catch-up
    assert skip_stale_catchup([e], now=NOW, grace_s=60) == ["scrape-y"]


# --- heartbeat writer di scheduler ----------------------------------------------


class _SetRecorder:
    def __init__(self, fail: bool = False) -> None:
        self.calls: list[tuple[str, str]] = []
        self.fail = fail

    def set(self, key: str, value: str) -> None:
        if self.fail:
            raise ConnectionError("redis mati")
        self.calls.append((key, value))


def _bare_scheduler(client: _SetRecorder) -> object:
    from cti_worker.scheduler import CtiScheduler

    sched = object.__new__(CtiScheduler)  # tanpa setup_schedule/shelve
    sched._redis = client
    sched._started_at = NOW
    sched._last_heartbeat = 0.0
    return sched


def test_scheduler_writes_heartbeat_throttled() -> None:
    client = _SetRecorder()
    sched = _bare_scheduler(client)

    sched._maybe_heartbeat()  # type: ignore[attr-defined]
    sched._maybe_heartbeat()  # type: ignore[attr-defined]  # < 15 dtk -> di-skip

    assert len(client.calls) == 1
    key, value = client.calls[0]
    assert key == beat_heartbeat.HEARTBEAT_KEY
    hb = beat_heartbeat.parse(value)
    assert hb is not None and hb.started_at == NOW


def test_heartbeat_failure_never_breaks_the_beat_loop() -> None:
    sched = _bare_scheduler(_SetRecorder(fail=True))
    sched._maybe_heartbeat()  # type: ignore[attr-defined]  # gak raise


def test_celery_app_uses_the_custom_scheduler() -> None:
    from cti_worker.celery_app import app

    assert app.conf.beat_scheduler == "cti_worker.scheduler:CtiScheduler"
    assert app.conf.beat_max_interval <= 60


# --- watchdog (di worker) -------------------------------------------------------


class _FakeSyncRedis:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self.data.get(key)

    def set(self, key: str, value: str, *, nx: bool = False, ex: int | None = None) -> bool:
        if nx and key in self.data:
            return False
        self.data[key] = value
        return True

    def delete(self, key: str) -> int:
        return 1 if self.data.pop(key, None) is not None else 0


def _check(client: _FakeSyncRedis, sent: list[str], now: datetime.datetime = NOW) -> str:
    from cti_worker.beat_watchdog import check_once

    return check_once(
        client,
        now=now,
        stale_after_s=300,
        repeat_s=3600,
        send=lambda topic, msg: sent.append(f"{topic}|{msg}"),
    )


def test_watchdog_alerts_once_while_stale_then_reports_recovery() -> None:
    client = _FakeSyncRedis()
    sent: list[str] = []
    client.data[beat_heartbeat.HEARTBEAT_KEY] = beat_heartbeat.encode(
        NOW - datetime.timedelta(hours=2), None
    )

    assert _check(client, sent) == "stale_alerted"
    assert _check(client, sent) == "stale_suppressed"  # worker lain / putaran berikutnya
    assert len(sent) == 1
    assert sent[0].startswith("scraper_health|") and "MATI" in sent[0]

    client.data[beat_heartbeat.HEARTBEAT_KEY] = beat_heartbeat.encode(NOW, None)
    assert _check(client, sent) == "recovered"
    assert _check(client, sent) == "ok"
    assert len(sent) == 2 and "PULIH" in sent[1]


def test_watchdog_treats_missing_heartbeat_as_down() -> None:
    client = _FakeSyncRedis()
    sent: list[str] = []
    assert _check(client, sent) == "stale_alerted"
    assert "tidak pernah" in sent[0]


def test_watchdog_quiet_when_healthy() -> None:
    client = _FakeSyncRedis()
    sent: list[str] = []
    client.data[beat_heartbeat.HEARTBEAT_KEY] = beat_heartbeat.encode(NOW, None)
    assert _check(client, sent) == "ok"
    assert sent == []


def test_watchdog_disabled_in_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    from cti_worker import beat_watchdog

    monkeypatch.setenv("ENVIRONMENT", "dev")
    assert beat_watchdog.start() is False


# --- next run ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cron", "expected"),
    [
        ("0 0 * * 1", datetime.datetime(2026, 10, 5, 0, 0, tzinfo=UTC)),  # Senin berikutnya
        ("5-59/15 * * * *", datetime.datetime(2026, 9, 30, 17, 20, tzinfo=UTC)),
        ("17 * * * *", datetime.datetime(2026, 9, 30, 18, 17, tzinfo=UTC)),  # 17:17 udah lewat
        ("0 0/1 * * *", datetime.datetime(2026, 9, 30, 18, 0, tzinfo=UTC)),  # bentuk `0/N` (eset)
    ],
)
def test_next_run(cron: str, expected: datetime.datetime) -> None:
    assert next_run(cron, now=NOW) == expected


def test_next_run_invalid_cron_is_none() -> None:
    assert next_run("bukan cron", now=NOW) is None
