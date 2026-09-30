"""`cti_scraper.sinks._enrich_queue_depth` lawan Redis + producer Celery ASLI.

Guard backpressure (Fase 10.1e) bergantung ke SATU asumsi yang gak bisa
diverifikasi lewat fake: Celery+Redis nyimpen queue `enrich` sebagai LIST
bernama persis `enrich`, jadi `LLEN enrich` = jumlah pesan yang belum diambil
worker. Kalau kombu suatu saat ganti skema key (mis. priority suffix), guard
diam-diam selalu lihat 0 -- test ini yang bakal teriak duluan.
"""

from __future__ import annotations

import pytest
import redis
from celery import Celery
from cti_scraper import sinks


@pytest.fixture(autouse=True)
def _clean(redis_client: redis.Redis) -> None:
    redis_client.flushall()


def _producer(redis_client: redis.Redis) -> Celery:
    kw = redis_client.connection_pool.connection_kwargs
    app = Celery("t", broker=f"redis://{kw['host']}:{kw['port']}/{kw.get('db', 0)}")
    app.conf.task_ignore_result = True
    return app


def test_llen_counts_messages_sent_with_send_task(
    redis_client: redis.Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sinks, "_broker_redis", lambda: redis_client)
    app = _producer(redis_client)
    assert sinks._enrich_queue_depth() == 0

    for n in range(3):
        app.send_task("enrich.article", kwargs={"url": f"https://x/{n}"}, queue="enrich")
    app.send_task("scrape.run", args=("x",), queue="scrape.rss")  # queue lain: gak ikut

    assert sinks._enrich_queue_depth() == 3


def test_ensure_capacity_raises_once_depth_reaches_the_limit(
    redis_client: redis.Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    monkeypatch.setattr(sinks, "_broker_redis", lambda: redis_client)
    monkeypatch.setattr(
        sinks,
        "get_settings",
        lambda: SimpleNamespace(scraper=SimpleNamespace(enrich_queue_max_depth=3)),
    )
    app = _producer(redis_client)

    for n in range(2):
        app.send_task("enrich.article", kwargs={"url": f"https://x/{n}"}, queue="enrich")
    sinks.ensure_enrich_capacity()  # 2 < 3: lolos

    app.send_task("enrich.article", kwargs={"url": "https://x/2"}, queue="enrich")
    with pytest.raises(sinks.BackpressureError, match="3 >= batas 3"):
        sinks.ensure_enrich_capacity()
