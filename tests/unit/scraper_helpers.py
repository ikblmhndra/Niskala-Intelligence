"""Alat bantu test scraper bespoke (Fase 10.E): `ScrapeContext` dengan transport
HTTP palsu, jadi `fetch()` bisa dijalankan tanpa jaringan dan tanpa DB."""

from __future__ import annotations

import datetime
from collections.abc import Callable
from typing import Any

import httpx
import structlog
from cti_scraper.base import BaseScraper, ScrapeContext
from cti_scraper.http import ScraperHttpClient

NOW = datetime.datetime(2026, 9, 26, 12, 0, 0)


def make_ctx(
    cls: type[BaseScraper],
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    now: datetime.datetime = NOW,
    reference: dict[str, Any] | None = None,
    options: dict[str, str] | None = None,
) -> ScrapeContext:
    http = ScraperHttpClient(transport=httpx.MockTransport(handler), rate_limit="10000/minute")
    return ScrapeContext(
        meta=cls.meta,
        run_id="test",
        http=http,
        log=structlog.get_logger(),
        now=now,
        reference=reference or {},
        options=options or {},
    )


def json_response(payload: Any, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=payload)
