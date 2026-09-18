"""Task `scrape.run` -- eksekusi SATU scraper. Beat (`cti_worker.beat`)
manggil ini terjadwal per scraper (`args=(scraper_id,)`, `queue=` dinamis
lewat `cti_worker.queues.queue_for`); control plane (Fase 9, trigger
manual) bakal manggil task yang sama.

Retry di LEVEL TASK (whole run), bukan per-request -- `ScraperHttpClient`
(Fase 3) sengaja gak retry sendiri per `httpx.get()`, dan `Runner`
(`runner.py`) sengaja NANGKEP `TransientFetchError`/`RateLimited` jadi
`RunResult.status`, bukan biarin exception nembus (baca docstring
`Runner._run_body`: "runner ini SENGAJA gak retry sendiri; caller yang
urus"). Task ini itu "caller"-nya: cek `result.status`, raise
`_RetryableRunError` biar `autoretry_for` Celery yang eksekusi backoff --
`ParseError` (situs berubah) TIDAK PERNAH masuk sini, `status="parse_error"`
dibiarin apa adanya (retry gak bakal ngubah hasil situs yang emang berubah)."""

from __future__ import annotations

from typing import Any

import structlog

from cti_worker.celery_app import app

log = structlog.get_logger()


class _RetryableRunError(Exception):
    """Sinyal internal ke `autoretry_for` -- bukan exception yang
    Runner/scraper lempar, murni buat nge-trigger retry Celery dari
    `RunResult.status` yang udah dikembaliin bersih."""


@app.task(
    bind=True,
    name="scrape.run",
    autoretry_for=(_RetryableRunError,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
)
def run_scraper(self: Any, scraper_id: str) -> dict[str, object]:
    from cti_core.config import get_settings
    from cti_core.db.engine import sync_session
    from cti_scraper.ratelimit import TokenBucket
    from cti_scraper.registry import discover
    from cti_scraper.runner import Runner

    registry = discover()
    scraper_cls = registry.get(scraper_id)
    if scraper_cls is None:
        # ID gak ketemu (typo di beat schedule, atau scraper udah dihapus
        # tapi jadwal lama masih ke-generate) -- fail keras, JANGAN retry,
        # retry gak bakal bikin scraper itu muncul.
        raise ValueError(f"scraper '{scraper_id}' gak ketemu di registry")

    settings = get_settings()
    import redis as redis_lib

    bucket = TokenBucket(redis_lib.Redis.from_url(settings.redis.url))

    with sync_session() as session:
        result = Runner(scraper_cls, session=session, bucket=bucket, dry_run=False).execute(
            trigger="beat"
        )

    if result.status in ("fetch_error", "rate_limited"):
        log.warning(
            "scrape_task_retrying",
            scraper_id=scraper_id,
            status=result.status,
            attempt=self.request.retries,
        )
        raise _RetryableRunError(f"{scraper_id}: {result.status}")

    return {
        "scraper_id": scraper_id,
        "status": result.status,
        "items_found": result.items_found,
        "items_new": result.items_new,
    }
