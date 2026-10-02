"""Request yang MENUNGGU budget rate-limit lokal reset, bukan langsung gagal.

Untuk scraper bespoke yang satu run-nya memukul puluhan sampai ratusan request ke domain yang sama
(`github_poc_monitor`: 1 search per CVE ter-track + 1 call MITRE per kandidat; `new_cve`: 1 call NVD +
1 Tenable per techstack + 1 call MITRE per kandidat CVE). Budget domain (`TokenBucket`, fixed-window,
dibagi semua scraper yang memukul host itu) jauh lebih kecil dari jumlah request satu run, dan
`ScraperHttpClient.get` melempar `RateLimited` begitu budget habis -- tanpa menunggu:

  - run mati `rate_limited` di request ke-N, kandidat yang urutannya di belakang gak pernah kebagian
    (staging 2026-10-01: `github_poc_monitor` 76 run 0 sukses, `new_cve` 22 dari 44 run mati di MITRE);
  - kalau `RateLimited` ketelan `except Exception` (mis. `_mitre_vendor_product`), hasilnya diam-diam
    "Unknown" dan kandidat dibuang filter berikutnya tanpa jejak.

Script lama pakai `time.sleep` manual antar request. Di sini: tunggu sampai jendela fixed-window RESET
(`window_s` dari `ctx.meta.rate_limit` -- deterministik, bukan tebakan), ulang maks `RATE_RETRIES` kali.
Pola yang sama sudah ada di `cti_scrapers.collectors._twitterapi._get_with_backoff` (yang juga
menangani 429 dari server -- beda kasus, tetap terpisah)."""

from __future__ import annotations

import time

import httpx
from cti_scraper.base import ScrapeContext
from cti_scraper.errors import RateLimited
from cti_scraper.ratelimit import parse_rate

RATE_RETRIES = 5
"""Maks berapa kali SATU request menunggu jendela reset sebelum menyerah (`RateLimited` diteruskan)."""


def get_waiting(ctx: ScrapeContext, url: str) -> httpx.Response:
    for attempt in range(RATE_RETRIES + 1):
        try:
            return ctx.http.get(url)
        except RateLimited:
            if attempt == RATE_RETRIES:
                raise
            _, window_s = parse_rate(ctx.meta.rate_limit)
            ctx.log.info("budget lokal abis, menunggu jendela reset", url=url[:80], wait_s=window_s)
            time.sleep(window_s)
    raise AssertionError("tak tercapai")  # pragma: no cover
