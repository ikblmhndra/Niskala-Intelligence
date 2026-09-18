"""Task `enrich.article` -- gantiin tulis-langsung `_article_sink` (Fase 3).
`fetch()` scraper mana pun yang nge-`yield` `ArticleItem` sekarang mendarat
di sini via `send_task`, bukan `ArticleRepo.upsert()` langsung -- lihat
`cti_scraper.sinks._article_sink` (Fase 6), kontrak "tipe apa masuk situ"
gak berubah, cuma titik tulisnya pindah dari sink SINKRON ke task ASINKRON.

Import `cti_enrich` (spaCy/sumy) LAZY di dalam fungsi -- baca docstring
`cti_worker.celery_app` soal kenapa (worker scrape-only, image tanpa extra
`nlp`, tetep bisa start walau task ini gak pernah beneran dia jalanin).

Retry CUMA buat `json.JSONDecodeError` yang lolos dari retry internal
`classify()`/`extract_ttps()` (masing-masing udah 3x percobaan sendiri,
lihat `cti_enrich.stages.classify._MAX_ATTEMPTS` -- residual ~6.5% di
korpus test Fase 5, murni reliability gateway LLM). `OpenAIQuotaExhausted`
SENGAJA gak di-retry -- kuota abis gak bakal pulih dalam hitungan detik,
retry cuma nge-spam queue; task gagal, keliatan di log/monitoring, butuh
tindakan manusia."""

from __future__ import annotations

import datetime
import json
from typing import Any

import structlog

from cti_worker.celery_app import app

log = structlog.get_logger()


@app.task(
    bind=True,
    name="enrich.article",
    queue="enrich",
    autoretry_for=(json.JSONDecodeError,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=2,
)
def enrich_article(
    self: Any,
    *,
    title: str,
    url: str,
    posted_on: str | None,
    source: str,
    scraper_id: str | None,
) -> dict[str, object]:
    from cti_core.db.engine import sync_session
    from cti_enrich.pipeline import run_pipeline

    parsed_posted_on = datetime.date.fromisoformat(posted_on) if posted_on else None

    with sync_session() as session:
        # `sync_session()` commit otomatis pas keluar `with` tanpa
        # exception (lihat db/engine.py) -- gak perlu commit manual di sini.
        outcome = run_pipeline(
            title=title,
            url=url,
            posted_on=parsed_posted_on,
            source=source,
            scraper_id=scraper_id,
            session=session,
        )

    log.info(
        "enrich_task_done",
        url=url,
        accepted=outcome.accepted,
        news_type=outcome.news_type,
    )
    return {"accepted": outcome.accepted, "news_type": outcome.news_type}
