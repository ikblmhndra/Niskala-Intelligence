"""Client HTTP bersama -- dipakai lewat `ctx.http`. UA, timeout, retry, dan
rate limit per-domain udah diset di sini; scraper gak perlu (dan gak boleh)
bikin `httpx.Client`/`requests.Session` sendiri.

`transport` bisa disuntik (`httpx.MockTransport`) buat golden test --
itu yang bikin scraper bisa dites lawan byte HTTP yang direkam Fase 0
tanpa nyentuh jaringan sama sekali. Lihat tests/contract/.
"""

from __future__ import annotations

from typing import Any

import httpx

from cti_scraper.errors import RateLimited, TransientFetchError
from cti_scraper.ratelimit import TokenBucket, parse_rate

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (compatible; cti-platform/0.1; +https://github.com/anthropics/cti-platform) httpx"
)


class ScraperHttpClient:
    def __init__(
        self,
        *,
        timeout_s: float = 30.0,
        rate_limit: str = "20/minute",
        user_agent: str = DEFAULT_USER_AGENT,
        bucket: TokenBucket | None = None,
        transport: httpx.BaseTransport | None = None,
        default_headers: dict[str, str] | None = None,
    ) -> None:
        """`default_headers` -- header auth per-scraper (lihat
        `cti_scraper.credentials`), nempel di SETIAP request client ini.
        Scraper publik (mayoritas) gak pernah set ini."""
        self._client = httpx.Client(
            timeout=timeout_s,
            headers={"User-Agent": user_agent, **(default_headers or {})},
            follow_redirects=True,
            transport=transport,
        )
        self._bucket = bucket
        self._rate_limit = rate_limit

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        self._check_rate_limit(url)
        try:
            resp = self._client.get(url, **kwargs)
        except httpx.TimeoutException as e:
            raise TransientFetchError(f"timeout: {url}") from e
        except httpx.ConnectError as e:
            raise TransientFetchError(f"connection error: {url}") from e
        except httpx.RemoteProtocolError as e:
            raise TransientFetchError(f"protocol error: {url}") from e
        self._raise_for_transient_status(resp)
        return resp

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        self._check_rate_limit(url)
        try:
            resp = self._client.post(url, **kwargs)
        except httpx.TimeoutException as e:
            raise TransientFetchError(f"timeout: {url}") from e
        except httpx.ConnectError as e:
            raise TransientFetchError(f"connection error: {url}") from e
        self._raise_for_transient_status(resp)
        return resp

    def _check_rate_limit(self, url: str) -> None:
        if self._bucket is None:
            return
        domain = httpx.URL(url).host
        if not self._bucket.acquire(domain, self._rate_limit):
            # `retry_after` = panjang jendela fixed-window (batas atas waktu sampai
            # budget reset) -- dipakai task `scrape.run` buat jeda retry yang
            # masuk akal, bukan 1-2 dtk yang pasti kena limit yang sama (QA BUG-D6).
            _, window_s = parse_rate(self._rate_limit)
            raise RateLimited(
                f"rate limit domain '{domain}' abis ({self._rate_limit})",
                retry_after=float(window_s),
            )

    @staticmethod
    def _raise_for_transient_status(resp: httpx.Response) -> None:
        """5xx dan 429 itu worth di-retry -- BUKAN 4xx lain (401/403/404
        itu situsnya emang nolak/gak ada, retry gak bakal ngubah apa-apa).
        Perekam fixture Fase 0 pakai heuristik yang sama buat nandain
        'BLOCKED' -- lihat tools/salvage/record_fixtures.py."""
        if resp.status_code == 429 or resp.status_code >= 500:
            raise TransientFetchError(f"HTTP {resp.status_code}: {resp.request.url}")

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> ScraperHttpClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
