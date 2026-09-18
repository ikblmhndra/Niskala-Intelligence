"""Stage: ambil teks artikel dari URL -- port gabungan dua path yang di kode
lama kebetulan sama-sama "ambil isi artikel" tapi lewat DUA library beda:

- Jalur cepat `nlp.py:296-309`: `requests.get()` + `sumy.HtmlParser` (HTML
  DOM lawas, gampang gagal di halaman JS-heavy).
- Jalur fallback `ttpValidator.fetch_article_text()`: Playwright render +
  `newspaper3k` parse, dipanggil pas jalur cepat exception apa pun.

`cti-enrich` udah scaffold `trafilatura` dari Fase 1 (base dependency, bukan
di balik extra `nlp`) -- justru itu alasannya: satu library ekstraksi teks
buat DUA jalur (HTTP langsung, atau HTML hasil render Playwright), bukan
sumy-buat-ekstraksi (nyasar, sumy harusnya cuma buat *summarize*, lihat
`summarize.py`) + newspaper3k terpisah. `_full_article_text` (var lama)
sekarang JADI nilai balik stage ini -- gak ada lagi `_full_article_text or
result` di caller, karena `result` (ringkasan) sekarang stage lain
(`summarize.py`) yang SELALU jalan di atas apa pun yang stage ini hasilin."""

from __future__ import annotations

from configparser import ConfigParser

import trafilatura
from playwright.sync_api import sync_playwright

_USER_AGENT = "Mozilla/5.0"
_HTTP_TIMEOUT_S = 30
_PLAYWRIGHT_TIMEOUT_MS = 30_000
_PLAYWRIGHT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/91.0.4472.124 Safari/537.36"
)


def _fetch_rendered_html(url: str) -> str:
    """Fallback JS-heavy -- port `ttpValidator.fetch_article_text`'s
    Playwright render, minus parsing (extraction diserahkan ke trafilatura,
    satu library buat dua jalur, lihat docstring modul)."""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True, args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
            )
            page = browser.new_page()
            page.set_extra_http_headers({"User-Agent": _PLAYWRIGHT_USER_AGENT})
            page.goto(url, timeout=_PLAYWRIGHT_TIMEOUT_MS)
            content = page.content()
            browser.close()
        return content
    except Exception:
        return ""


def fetch_text(url: str) -> str:
    """Best-effort teks artikel penuh. String kosong kalau dua-duanya gagal
    -- caller (`pipeline.py`) yang mutusin gimana nanganin artikel tanpa
    teks (skip extract_ttps/score, persis kode lama waktu `result` kosong)."""
    downloaded = trafilatura.fetch_url(url, config=_trafilatura_config())
    if downloaded:
        text = trafilatura.extract(downloaded) or ""
        if text:
            return text

    html = _fetch_rendered_html(url)
    if html:
        return trafilatura.extract(html) or ""
    return ""


def _trafilatura_config() -> ConfigParser:
    cfg = trafilatura.settings.use_config()
    cfg.set("DEFAULT", "USER_AGENTS", _USER_AGENT)
    cfg.set("DEFAULT", "DOWNLOAD_TIMEOUT", str(_HTTP_TIMEOUT_S))
    return cfg
