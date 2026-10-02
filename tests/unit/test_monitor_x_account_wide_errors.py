"""Fase 10.D (2026-10-01): `monitor_x` diam-diam `empty` waktu kredit twitterapi.io habis.

`_fetch_tweets_for_account` cuma `log.warning` + `break` untuk SEMUA status non-200 (port perilaku
script lama). 401/402/403 itu masalah kredensial/kuota yang berlaku ke semua akun, bukan
satu akun -- di staging 262 run/hari berstatus `empty` tanpa pesan error. Sekarang gagal keras
(`ParseError`), sama kayak `tweet_alerts_*` dan `trending_cve`; error per-akun lain (mis. 404)
tetap cuma di-log.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from cti_scraper.errors import ParseError
from cti_scrapers.feeds import monitor_x as mod
from cti_scrapers.feeds.monitor_x import MonitorX

from tests.unit.scraper_helpers import make_ctx


def _ctx() -> Any:
    return make_ctx(MonitorX, lambda r: httpx.Response(200))


@pytest.mark.parametrize("status", [401, 402, 403])
def test_error_kredensial_atau_kuota_gagal_keras(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    body = '{"error":"Unauthorized","message":"Credits is not enough.Please recharge"}'
    monkeypatch.setattr(
        mod._twitterapi, "_get_with_backoff", lambda ctx, params: httpx.Response(status, text=body)
    )

    with pytest.raises(ParseError, match=f"HTTP {status}.*Credits is not enough"):
        mod._fetch_tweets_for_account(_ctx(), "someaccount", None)


def test_error_per_akun_lain_tetap_cuma_dilog(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        mod._twitterapi, "_get_with_backoff", lambda ctx, params: httpx.Response(404, text="gone")
    )

    assert mod._fetch_tweets_for_account(_ctx(), "someaccount", None) == []


def test_status_200_tetap_mengembalikan_tweet(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"tweets": [{"id": "1", "text": "hi"}], "has_next_page": False}
    monkeypatch.setattr(
        mod._twitterapi, "_get_with_backoff", lambda ctx, params: httpx.Response(200, json=payload)
    )

    assert mod._fetch_tweets_for_account(_ctx(), "someaccount", None) == payload["tweets"]
