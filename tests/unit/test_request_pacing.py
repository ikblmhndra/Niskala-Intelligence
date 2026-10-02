"""Fase 10.D (2026-10-01): `github_poc_monitor` dan `new_cve` mati `rate_limited` di staging.

Satu run memukul puluhan-ratusan request ke domain yang sama (`github_poc_monitor`: ~100 -- 1 search
per CVE ter-track + 1 call MITRE per kandidat; `new_cve`: 1 NVD + 1 Tenable per techstack + 1 MITRE
per kandidat) padahal budget domain 30-60/menit, dan `ctx.http.get` melempar `RateLimited` begitu
budget habis. Hasilnya: run mati di request ke-N (staging: `github_poc_monitor` 76 run 0 sukses,
`new_cve` 22 dari 44 run), kandidat di belakang gak pernah kebagian, dan `RateLimited` dari MITRE
ketelan `except Exception` di `github_poc_monitor` jadi vendor "Unknown" -> kandidat dibuang tanpa
jejak. `get_waiting` menunggu jendela reset lalu mengulang.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import httpx
import pytest
from cti_scraper.errors import RateLimited
from cti_scrapers.feeds import _pacing as pacing
from cti_scrapers.feeds import github_poc_monitor as poc
from cti_scrapers.feeds.github_poc_monitor import GithubPocMonitor
from cti_scrapers.feeds.new_cve import NewCve

from tests.unit.scraper_helpers import make_ctx


class _FakeHttp:
    """`get(url)`: tiap URL kena `RateLimited` sebanyak `limited_first` kali dulu, baru berhasil.
    Isi respons dipilih dari `routes` (potongan URL -> dict JSON atau bytes mentah)."""

    def __init__(self, routes: dict[str, Any], *, limited_first: int = 0) -> None:
        self.routes = routes
        self.limited_first = limited_first
        self.calls: list[str] = []
        self._limited: dict[str, int] = {}

    def get(self, url: str, **_: Any) -> httpx.Response:
        self.calls.append(url)
        done = self._limited.get(url, 0)
        if done < self.limited_first:
            self._limited[url] = done + 1
            raise RateLimited("budget habis")
        for needle, body in self.routes.items():
            if needle in url:
                if isinstance(body, bytes):
                    return httpx.Response(200, content=body)
                return httpx.Response(200, json=body)
        return httpx.Response(200, json={})


@pytest.fixture
def sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    recorded: list[float] = []
    monkeypatch.setattr(pacing.time, "sleep", recorded.append)
    return recorded


def _ctx(cls: Any, http: _FakeHttp, reference: dict[str, Any] | None = None) -> Any:
    ctx = make_ctx(cls, lambda r: httpx.Response(200), reference=reference or {})
    ctx.http = http
    return ctx


# ---- get_waiting ---------------------------------------------------------------------------


def test_get_waiting_menunggu_jendela_reset_lalu_mengulang(sleeps: list[float]) -> None:
    http = _FakeHttp({"": {"ok": True}}, limited_first=2)

    resp = pacing.get_waiting(_ctx(GithubPocMonitor, http), "https://api.github.com/x")

    assert resp.json() == {"ok": True}
    assert len(http.calls) == 3
    assert sleeps == [60, 60]  # "30/minute" -> jendela 60 dtk


def test_get_waiting_lama_tunggu_diambil_dari_rate_limit_scraper_bukan_hardcode(
    sleeps: list[float],
) -> None:
    http = _FakeHttp({"": {}}, limited_first=2)
    ctx = _ctx(GithubPocMonitor, http)
    ctx.meta = dataclasses.replace(ctx.meta, rate_limit="5/second")

    pacing.get_waiting(ctx, "https://api.github.com/x")

    assert sleeps == [1, 1]


def test_get_waiting_menyerah_setelah_batas_percobaan(sleeps: list[float]) -> None:
    http = _FakeHttp({"": {}}, limited_first=999)

    with pytest.raises(RateLimited):
        pacing.get_waiting(_ctx(GithubPocMonitor, http), "https://api.github.com/x")

    assert len(http.calls) == pacing.RATE_RETRIES + 1
    assert len(sleeps) == pacing.RATE_RETRIES


# ---- github_poc_monitor ----------------------------------------------------------------------


def test_github_targeted_menjangkau_semua_cve_walau_tiap_request_kena_limit(
    sleeps: list[float],
) -> None:
    cves = [f"CVE-2026-{n:04d}" for n in range(1, 6)]
    repo = {
        "html_url": "https://github.com/x/poc",
        "name": "cve-2026-poc",
        "description": "",
        "fork": False,
        "owner": {"login": "x"},
    }
    http = _FakeHttp({"search/repositories": {"items": [repo]}}, limited_first=1)
    ctx = _ctx(
        GithubPocMonitor,
        http,
        {"true_positive_cves": [{"cve_id": c, "poc_urls": set()} for c in cves]},
    )

    list(GithubPocMonitor()._targeted_search(ctx))

    searched = {c for c in cves for url in http.calls if f"q={c}+" in url}
    assert searched == set(cves)
    assert len(sleeps) == len(cves)  # satu tunggu per CVE (tiap URL kena limit sekali)


def test_github_mitre_menunggu_alih_alih_diam_diam_jadi_unknown(sleeps: list[float]) -> None:
    body = {"containers": {"cna": {"affected": [{"vendor": "Fortinet", "product": "FortiOS"}]}}}
    http = _FakeHttp({"cveawg.mitre.org": body}, limited_first=1)

    vendor, product = poc._mitre_vendor_product(_ctx(GithubPocMonitor, http), "cve-2026-0001")

    assert (vendor, product) == ("Fortinet", "FortiOS")
    assert sleeps == [60]


def test_github_broad_juga_menunggu_per_request(sleeps: list[float]) -> None:
    http = _FakeHttp({"search/repositories": {"items": []}}, limited_first=1)
    ctx = _ctx(GithubPocMonitor, http, {"techstack": ["fortinet"]})

    assert list(GithubPocMonitor()._broad_search(ctx)) == []

    # dua tahun (tahun ini + tahun lalu), tiap halaman pertama kena limit sekali lalu berhasil
    assert len(sleeps) == 2
    assert len(http.calls) == 4


# ---- new_cve ---------------------------------------------------------------------------------


def test_new_cve_selesai_walau_nvd_tenable_dan_mitre_masing_masing_kena_limit(
    sleeps: list[float],
) -> None:
    routes = {
        "services.nvd.nist.gov": {
            "vulnerabilities": [
                {
                    "cve": {
                        "id": "CVE-2026-1111",
                        "descriptions": [{"lang": "en", "value": "fortinet bug"}],
                    }
                }
            ]
        },
        "tenable.com": b"<html><body></body></html>",
        "cveawg.mitre.org": {
            "containers": {"cna": {}},
            "cveMetadata": {"datePublished": "2026-09-30T00:00:00Z"},
        },
    }
    http = _FakeHttp(routes, limited_first=1)
    ctx = _ctx(
        NewCve,
        http,
        {"techstack": ["fortinet"], "techstack_by_client": {"acme": ["fortinet"]}},
    )

    items = list(NewCve().fetch(ctx))

    assert [(i.cve_id, i.client_id) for i in items] == [("CVE-2026-1111", "acme")]
    assert sleeps == [60, 60, 60]  # NVD, Tenable, MITRE: masing-masing tunggu sekali ("60/minute")
