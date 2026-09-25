"""Task `scrape.run` -- eksekusi SATU scraper. Beat (`cti_worker.beat`)
manggil ini terjadwal per scraper (`args=(scraper_id,)`, `trigger` default
"beat", `queue=` dinamis lewat `cti_worker.queues.queue_for`); control
plane (Fase 9, `POST /api/scraper/{id}/trigger`) manggil task YANG SAMA
lewat `.delay(scraper_id, trigger="manual")` -- `Runner`/`ScraperRun.
trigger` yang bedain asalnya, bukan task terpisah.

Retry di LEVEL TASK (whole run), bukan per-request -- `ScraperHttpClient`
(Fase 3) sengaja gak retry sendiri per `httpx.get()`, dan `Runner`
(`runner.py`) sengaja NANGKEP `TransientFetchError`/`RateLimited` jadi
`RunResult.status`, bukan biarin exception nembus (baca docstring
`Runner._run_body`: "runner ini SENGAJA gak retry sendiri; caller yang
urus"). Task ini itu "caller"-nya: cek `result.status`, raise
`_RetryableRunError` biar `autoretry_for` Celery yang eksekusi backoff --
`ParseError` (situs berubah) TIDAK PERNAH masuk sini, `status="parse_error"`
dibiarin apa adanya (retry gak bakal ngubah hasil situs yang emang berubah).

Task `scraper.purge_expired_items`/`scraper.purge_expired_seen` (Fase 9,
`maintenance` queue) numpang file ini juga -- sama domain (scraper), sync
native (bukan `_run_async()` kayak `tasks/periodic.py`, soalnya manggil
repo SYNC langsung, gak ada layer `cti_api.services` async yang dibungkus)."""

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
def run_scraper(self: Any, scraper_id: str, trigger: str = "beat") -> dict[str, object]:
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
            trigger=trigger
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


@app.task(bind=True, name="scraper.purge_expired_items", queue="maintenance")
def purge_expired_items(self: Any) -> dict[str, object]:
    from cti_core.db.engine import sync_session
    from cti_core.db.repositories.scraper import ScraperItemRepo

    with sync_session() as session:
        deleted = ScraperItemRepo(session).purge_expired()
    log.info("scraper_items_purged", deleted=deleted)
    return {"deleted": deleted}


@app.task(bind=True, name="scraper.purge_expired_seen", queue="maintenance")
def purge_expired_seen(self: Any) -> dict[str, object]:
    """`scraper_seen.expire_at` udah ada dari Fase 2, tapi task ini gak
    pernah ditulis sampai Fase 9 -- baris in-flight (1 hari) dan committed
    (`dedup_ttl_days`, default 180) numpuk gak abis-abis dari hari pertama
    deploy sampai sekarang."""
    from cti_core.db.engine import sync_session
    from cti_core.db.repositories.scraper_seen import ScraperSeenRepo

    with sync_session() as session:
        deleted = ScraperSeenRepo(session).purge_expired()
    log.info("scraper_seen_purged", deleted=deleted)
    return {"deleted": deleted}


@app.task(bind=True, name="scraper.health_digest", queue="notify")
def scraper_health_digest(self: Any) -> dict[str, object]:
    """SATU pesan Telegram konsolidasi (topic `scraper_health`, perlu
    ditambahin ke `TELEGRAM__THREAD_IDS` operator) tiap sweep -- gantiin
    kelas masalah yang sama kayak 14 fungsi `send_alert_*` lama
    (`cti_alerts.telegram`'s docstring): satu alert per scraper bermasalah
    bakal jadi puluhan pesan kalau lagi ada insiden luas, di sini digabung
    jadi satu. GAK ngirim apa-apa kalau semua `ok`/`disabled` -- diam itu
    sinyal "sehat", bukan di-spam tiap tick."""
    from cti_alerts.telegram import send_alert
    from cti_core.db.engine import sync_session
    from cti_core.db.repositories.scraper import ScraperConfigRepo, ScraperRunRepo
    from cti_scraper.health import summarize_fleet_health
    from cti_scraper.registry import discover

    registry = discover()
    with sync_session() as session:
        configs = ScraperConfigRepo(session).get_all()
        recent_runs = ScraperRunRepo(session).list_recent_by_scraper_bulk(limit=3)

    entries = summarize_fleet_health(registry, configs, recent_runs)
    problems = [e for e in entries if e.status not in ("ok", "disabled")]
    if not problems:
        log.info("scraper_health_digest_clean", total=len(entries))
        return {"problems": 0, "total": len(entries)}

    by_status: dict[str, list[str]] = {}
    for e in problems:
        by_status.setdefault(e.status, []).append(f"{e.scraper_id} ({e.source})")

    lines = [f"<b>Scraper Health</b> -- {len(problems)}/{len(entries)} bermasalah"]
    for status in sorted(by_status):
        lines.append(f"\n<b>{status}</b> ({len(by_status[status])}):")
        lines.extend(f"  • {s}" for s in sorted(by_status[status]))

    send_alert("scraper_health", "\n".join(lines))
    log.info("scraper_health_digest_sent", problems=len(problems), total=len(entries))
    return {"problems": len(problems), "total": len(entries)}
