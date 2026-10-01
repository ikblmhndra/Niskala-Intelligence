"""QA BUG-D6 -- retry storm `scrape.run` (staging 2026-10-01: `monitor_x` 4 run `beat` dalam
~10 dtk tiap slot, 132 run vs 33 slot cron). Dikunci di sini:

- jeda retry 60/120/240 dtk (maks 600) dan gak pernah di bawah `retry_after`,
- run hasil retry dicatat `beat_retry`/`manual_retry`, bukan `beat` lagi,
- `RateLimited` dari token bucket lokal bawa `retry_after` = panjang jendela,
- `Runner` ngoper `retry_after` ke `RunResult`.
"""

from __future__ import annotations

import contextlib
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from cti_scraper.errors import RateLimited
from cti_scraper.http import ScraperHttpClient


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


def test_retry_countdown_backs_off_in_minutes_not_seconds() -> None:
    from cti_worker.tasks.scrape import retry_countdown

    assert [retry_countdown(n) for n in range(5)] == [60, 120, 240, 480, 600]
    assert retry_countdown(0, retry_after=90.5) == 90  # sisa jendela lebih lama dari backoff
    assert retry_countdown(2, retry_after=60) == 240


@pytest.mark.parametrize(
    ("trigger", "expected"),
    [("beat", "beat_retry"), ("manual", "manual_retry"), ("beat_retry", "beat_retry")],
)
def test_retry_trigger(trigger: str, expected: str) -> None:
    from cti_worker.tasks.scrape import retry_trigger

    assert retry_trigger(trigger) == expected
    assert len(retry_trigger(trigger)) <= 20  # ScraperRun.trigger String(20)


class _Retry(Exception):
    pass


def _run_task(
    monkeypatch: pytest.MonkeyPatch,
    *,
    status: str,
    retry_after: float | None = None,
    retries: int = 0,
    trigger: str = "beat",
) -> dict[str, Any]:
    """Jalanin body `scrape.run` dgn Runner/DB palsu; balikin argumen `self.retry` (atau hasil)."""
    from cti_worker.tasks import scrape

    class _FakeRunner:
        def __init__(self, *_a: object, **_kw: object) -> None:
            pass

        def execute(self, *, trigger: str) -> SimpleNamespace:
            _FakeRunner.trigger = trigger  # type: ignore[attr-defined]
            return SimpleNamespace(
                status=status, retry_after=retry_after, items_found=0, items_new=0
            )

    monkeypatch.setattr("cti_scraper.runner.Runner", _FakeRunner)
    monkeypatch.setattr("cti_scraper.registry.discover", lambda: {"x": object})
    monkeypatch.setattr("cti_core.db.engine.sync_session", lambda: contextlib.nullcontext(object()))
    captured: dict[str, Any] = {}

    def _fake_retry(**kwargs: Any) -> _Retry:
        captured.update(kwargs)
        return _Retry()

    monkeypatch.setattr(scrape.run_scraper, "retry", _fake_retry)
    scrape.run_scraper.push_request(retries=retries)
    try:
        captured["result"] = scrape.run_scraper.run("x", trigger=trigger)
    except _Retry:
        captured["retried"] = True
    finally:
        scrape.run_scraper.pop_request()
    captured["runner_trigger"] = _FakeRunner.trigger  # type: ignore[attr-defined]
    return captured


def test_rate_limited_run_is_retried_after_the_window_and_marked_as_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    out = _run_task(monkeypatch, status="rate_limited", retry_after=60.0)

    assert out["retried"] is True
    assert out["countdown"] == 60
    assert out["args"] == ("x",)
    assert out["kwargs"] == {"trigger": "beat_retry"}
    assert out["runner_trigger"] == "beat"  # run PERTAMA tetap tercatat `beat`


def test_second_retry_doubles_and_keeps_retry_trigger(monkeypatch: pytest.MonkeyPatch) -> None:
    out = _run_task(monkeypatch, status="fetch_error", retries=1, trigger="beat_retry")

    assert out["countdown"] == 120
    assert out["kwargs"] == {"trigger": "beat_retry"}
    assert out["runner_trigger"] == "beat_retry"


def test_parse_error_and_ok_are_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    for status in ("parse_error", "ok", "empty"):
        out = _run_task(monkeypatch, status=status)
        assert "retried" not in out
        assert out["result"]["status"] == status


class _EmptyBucket:
    def acquire(self, domain: str, rate: str) -> bool:
        return False


def test_local_rate_limit_carries_retry_after_window() -> None:
    http = ScraperHttpClient(
        rate_limit="10/minute",
        bucket=_EmptyBucket(),  # type: ignore[arg-type]
        transport=httpx.MockTransport(lambda r: httpx.Response(200)),
    )
    with pytest.raises(RateLimited) as exc:
        http.get("https://api.example.test/x")
    assert exc.value.retry_after == 60.0


def test_runner_passes_retry_after_into_result() -> None:
    from cti_scraper.base import BaseScraper, ScraperMeta
    from cti_scraper.runner import Runner

    class _Limited(BaseScraper):
        meta = ScraperMeta(id="limited_test", source="t", schedule="0 * * * *")

        def fetch(self, ctx: Any) -> Any:
            raise RateLimited("abis", retry_after=42.0)

    result = Runner(_Limited, dry_run=True).execute()

    assert result.status == "rate_limited"
    assert result.retry_after == 42.0
