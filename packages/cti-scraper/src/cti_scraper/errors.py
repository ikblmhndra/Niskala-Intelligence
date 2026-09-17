"""Exception yang framework tau cara nanganinnya. Scraper `fetch()` cuma
boleh raise ini (atau biarin exception biasa nembus -- runner tetap nangkep
tapi klasifikasi bakal jatuh ke "unknown"). Lihat runner.py.
"""

from __future__ import annotations


class ScraperError(Exception):
    """Base -- jangan di-raise langsung."""


class TransientFetchError(ScraperError):
    """5xx, timeout, connection reset -- worth di-retry. Bukan tanggung
    jawab scraper buat retry sendiri; raise ini, runner yang urus backoff."""


class RateLimited(ScraperError):
    """Token bucket domain abis. Biasanya dilempar framework sendiri
    (ctx.http), bukan kode scraper -- tapi scraper boleh raise ini kalau
    situs balikin 429 dan mau dipetakan eksplisit ke retry."""

    def __init__(self, message: str = "rate limited", *, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class ParseError(ScraperError):
    """Dokumen kebaca tapi strukturnya gak sesuai -- selector nggak match,
    field yang diharap gak ada. Ini artinya SITUS BERUBAH, bukan blip
    jaringan. JANGAN di-retry (tiga kali percobaan ulang cuma buang-buang
    fetch buat kegagalan yang gak bakal beda hasilnya) -- runner nyatet
    status="parse_error" dan langsung eskalasi ke health sweep.
    """
