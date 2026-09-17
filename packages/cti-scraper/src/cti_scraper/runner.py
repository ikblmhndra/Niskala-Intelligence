"""Eksekusi satu scraper end-to-end: rate-limit -> fetch -> dedup -> sink
-> heartbeat. Dipanggil CLI (Fase 3) dan nanti task Celery (Fase 6) --
signature sama, beda cuma siapa yang manggil dan gimana retry-nya diatur
(runner ini SENGAJA gak retry sendiri; caller yang urus, lihat plan §4.3).
"""

from __future__ import annotations

import time
import traceback
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import httpx
import structlog

from cti_scraper.base import BaseScraper, ScrapeContext
from cti_scraper.dedup import DedupStore
from cti_scraper.errors import ParseError, RateLimited, TransientFetchError
from cti_scraper.http import ScraperHttpClient
from cti_scraper.sinks import dispatch

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from cti_scraper.ratelimit import TokenBucket


class RunnerConfigError(Exception):
    """Runner dipanggil dengan kombinasi argumen yang gak masuk akal, mis.
    `dry_run=False` tanpa `session`."""


@dataclass
class RunResult:
    run_id: str
    scraper_id: str
    status: str
    """ok | empty | parse_error | fetch_error | rate_limited."""
    items_found: int = 0
    items_new: int = 0
    items_dropped: int = 0
    items_failed: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)
    duration_ms: int = 0


class Runner:
    def __init__(
        self,
        scraper_cls: type[BaseScraper],
        *,
        session: Session | None = None,
        bucket: TokenBucket | None = None,
        transport: httpx.BaseTransport | None = None,
        dry_run: bool = False,
    ) -> None:
        if not dry_run and session is None:
            raise RunnerConfigError(
                "dry_run=False butuh `session` -- runner nulis heartbeat+sink lewat itu"
            )
        self.scraper_cls = scraper_cls
        self.meta = scraper_cls.meta
        self.session = session
        self.bucket = bucket
        self.transport = transport
        self.dry_run = dry_run

    def execute(self, *, trigger: str = "manual") -> RunResult:
        run_id = str(uuid.uuid4())
        log = structlog.get_logger(scraper_id=self.meta.id, run_id=run_id, trigger=trigger)
        started = time.monotonic()

        run = None
        if not self.dry_run:
            from cti_core.db.repositories.scraper import ScraperRunRepo

            assert self.session is not None  # dijamin __init__
            run_repo = ScraperRunRepo(self.session)
            run = run_repo.start(run_id=run_id, scraper_id=self.meta.id, trigger=trigger)
            self.session.commit()

        result = self._run_body(run_id, log)

        if not self.dry_run:
            assert self.session is not None
            run_repo.finish(
                run,  # type: ignore[arg-type]
                status=result.status,
                items_found=result.items_found,
                items_new=result.items_new,
                items_dropped=result.items_dropped,
                items_failed=result.items_failed,
                errors=result.errors,
            )
            self.session.commit()

        result.duration_ms = int((time.monotonic() - started) * 1000)
        log.info(
            "run_finished",
            status=result.status,
            items_found=result.items_found,
            items_new=result.items_new,
            items_dropped=result.items_dropped,
            items_failed=result.items_failed,
            duration_ms=result.duration_ms,
        )
        return result

    def _run_body(self, run_id: str, log: structlog.typing.FilteringBoundLogger) -> RunResult:
        result = RunResult(run_id=run_id, scraper_id=self.meta.id, status="ok")

        default_headers = None
        if self.meta.credential is not None:
            from cti_scraper.credentials import resolve_credential_headers

            default_headers = resolve_credential_headers(self.meta.credential)

        http = ScraperHttpClient(
            timeout_s=self.meta.timeout_s,
            rate_limit=self.meta.rate_limit,
            bucket=self.bucket,
            transport=self.transport,
            default_headers=default_headers,
        )

        reference: dict[str, object] = {}
        if self.meta.reference_data:
            if self.session is None:
                raise RunnerConfigError(
                    f"scraper '{self.meta.id}' declare reference_data={self.meta.reference_data} "
                    "tapi gak ada `session` -- baca-baca DB internal tetap butuh session "
                    "walau dry_run=True (cuma sink/dedup yang di-skip pas dry-run)"
                )
            from cti_scraper.reference_data import resolve_reference_data

            reference = resolve_reference_data(self.meta.reference_data, self.session)

        ctx = ScrapeContext(meta=self.meta, run_id=run_id, http=http, log=log, reference=reference)
        scraper = self.scraper_cls()
        dedup = None if self.dry_run else DedupStore(self.session)  # type: ignore[arg-type]

        try:
            for item in scraper.fetch(ctx):
                result.items_found += 1
                self._handle_item(item, scraper, dedup, result, log)

            if result.items_found == 0:
                result.status = "empty"

        except ParseError as e:
            result.status = "parse_error"
            result.errors.append({"stage": "parse", "type": "ParseError", "message": str(e)})
            log.error("parse_error", error=str(e))
        except RateLimited as e:
            result.status = "rate_limited"
            result.errors.append({"stage": "fetch", "type": "RateLimited", "message": str(e)})
            log.warning("rate_limited", error=str(e))
        except TransientFetchError as e:
            result.status = "fetch_error"
            result.errors.append(
                {"stage": "fetch", "type": "TransientFetchError", "message": str(e)}
            )
            log.warning("transient_fetch_error", error=str(e))
        except Exception as e:
            result.status = "fetch_error"
            result.errors.append(
                {
                    "stage": "fetch",
                    "type": type(e).__name__,
                    "message": str(e),
                    "traceback": traceback.format_exc(),
                }
            )
            log.error("unhandled_fetch_error", error=str(e), error_type=type(e).__name__)
            scraper.on_run_error(e, ctx)
        finally:
            http.close()

        return result

    def _handle_item(
        self,
        item: object,
        scraper: BaseScraper,
        dedup: DedupStore | None,
        result: RunResult,
        log: structlog.typing.FilteringBoundLogger,
    ) -> None:
        if self.dry_run:
            return  # liat hasilnya doang -- gak dedup, gak sink

        assert dedup is not None and self.session is not None
        raw_key = scraper.dedup_key(item)  # type: ignore[arg-type]
        dedup_key: str | None = None
        if raw_key is not None:
            dedup_key = dedup.reserve(scraper_id=self.meta.id, raw_key=raw_key)
            if dedup_key is None:
                result.items_dropped += 1
                return  # duplikat, atau lease dipegang worker lain

        try:
            dispatch(item, self.meta, self.session)  # type: ignore[arg-type]
            self.session.commit()
            if dedup_key is not None:
                dedup.commit(dedup_key, ttl_days=self.meta.dedup_ttl_days)
            result.items_new += 1
        except Exception as e:
            self.session.rollback()
            if dedup_key is not None:
                dedup.release(dedup_key)
            result.items_failed += 1
            result.errors.append({"stage": "sink", "type": type(e).__name__, "message": str(e)})
            log.error("sink_failed", error=str(e), error_type=type(e).__name__)
