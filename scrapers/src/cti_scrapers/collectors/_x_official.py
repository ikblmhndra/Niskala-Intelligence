"""Adapter API RESMI X v2 (`GET /2/tweets/search/recent`) -- sumber Twitter ALTERNATIF,
dipilih per-scraper (lihat `_twitter.py`). Modul BUKAN scraper; awalan `_` = helper internal.

Autentikasi: bearer token app-only (`credential="x"` -> `Authorization: Bearer`),
dipasang `Runner`; modul ini tidak pernah memegang token.

BIAYA (pay-per-use): tiap tweet yang DIBACA ditagih `USD_PER_POST_READ`, dan request tanpa
hasil tidak menagih apa pun. Resource yang sama diminta lagi di hari UTC yang sama tidak
ditagih ulang -- jadi jendela pencarian yang tumpang-tindih (2x interval jadwal) aman.
Pengaman berlapis:
  - `MAX_PAGES` x `MAX_RESULTS` = batas keras tweet yang dibaca per run (200 ~ $1);
    sisa halaman DILEWATI dan dicatat (`x_official_truncated`), tweet yang lebih lama
    dari batas itu tidak terbaca.
  - Tiap pencarian mencatat jumlah tweet yang dibaca + perkiraan biayanya (`x_official_search`;
    hanya tweet -- objek user dari `expansions` kemungkinan ditagih terpisah, lihat
    `TweetSearch.with_author`).
  - Batas belanja bulanan: pasang di X Developer Console (di luar kode).

Perbedaan dari twitterapi.io yang dijembatani di sini: sintaks query (`-is:reply`,
param `start_time` ISO -- bukan `since_time:` di dalam query), username penulis harus
diminta lewat `expansions=author_id`, tweet panjang ada di `note_tweet` (teks utama
terpotong), dan teks datang HTML-escaped (`&amp;`) -- di-unescape supaya `html.escape`
di pesan Telegram tidak menggandakannya.
"""

from __future__ import annotations

import datetime
import html
from typing import Any

from cti_scraper.base import ScrapeContext
from cti_scraper.errors import ParseError

from cti_scrapers.collectors._twitter import Tweet, TweetSearch

SEARCH_URL = "https://api.x.com/2/tweets/search/recent"
MAX_RESULTS = 100
MAX_PAGES = 2
USD_PER_POST_READ = 0.005
"""Tarif dokumentasi X per September 2026 -- cuma buat perkiraan di log, bukan tagihan."""

_TWEET_FIELDS = "created_at,entities,referenced_tweets,note_tweet"


def compile_query(spec: TweetSearch) -> str:
    """Sintaks X v2. Waktu TIDAK di query -- lihat `start_time` di `_params`."""
    parts: list[str] = []
    if spec.accounts:
        parts.append("(" + " OR ".join(f"from:{a}" for a in spec.accounts) + ")")
    if spec.keyword:
        parts.append(spec.keyword)
    parts += ["-is:retweet", "-is:reply"]
    if spec.exclude_quotes:
        parts.append("-is:quote")
    return " ".join(parts)


def _params(spec: TweetSearch) -> dict[str, str]:
    params = {
        "query": compile_query(spec),
        "start_time": spec.since.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "max_results": str(MAX_RESULTS),
        "tweet.fields": _TWEET_FIELDS,
    }
    if spec.with_author:
        params["expansions"] = "author_id"
        params["user.fields"] = "username"
    return params


def search(ctx: ScrapeContext, spec: TweetSearch) -> list[Tweet]:
    """Tweet hasil `spec` (terbaru dulu), maksimal `MAX_PAGES` halaman.

    Status selain 200 = `ParseError` dengan judul/detail dari X (401 token salah, 402
    kredit habis, 403 tak punya akses, 400 query ditolak) -- BUKAN diam-diam nol tweet.
    429 dan 5xx sudah jadi `TransientFetchError` di `ScraperHttpClient` (Runner yang
    mengulang dengan backoff)."""
    params = _params(spec)
    tweets: list[Tweet] = []
    pages = 0
    next_token: str | None = None
    for _ in range(MAX_PAGES):
        if next_token:
            params["next_token"] = next_token
        resp = ctx.http.get(SEARCH_URL, params=params)
        pages += 1
        if resp.status_code != 200:
            raise ParseError(f"X API HTTP {resp.status_code}: {_error_summary(resp)}")
        try:
            payload = resp.json()
        except ValueError as e:
            raise ParseError(f"X API: respons bukan JSON valid -- {e}") from e
        page, next_token = parse_page(payload)
        tweets.extend(page)
        if not next_token:
            break

    ctx.log.info(
        "x_official_search",
        pages=pages,
        posts_read=len(tweets),
        est_cost_usd=round(len(tweets) * USD_PER_POST_READ, 4),
    )
    if next_token:
        ctx.log.warning(
            "x_official_truncated",
            reason=f"masih ada halaman setelah {MAX_PAGES} halaman ({MAX_RESULTS}/halaman); "
            "tweet yang lebih lama tidak terbaca run ini",
        )
    return tweets


def parse_page(payload: Any) -> tuple[list[Tweet], str | None]:
    """Satu halaman respons -> (tweet, next_token). Bentuk tak dikenal = `ParseError`."""
    if not isinstance(payload, dict):
        raise ParseError(f"X API: diharap objek JSON, dapat {type(payload).__name__}")
    if "data" not in payload and "meta" not in payload:
        raise ParseError(f"X API: respons tanpa 'data'/'meta' -- {str(payload)[:200]}")

    raw_items = payload.get("data") or []
    if not isinstance(raw_items, list):
        raise ParseError("X API: 'data' bukan list")
    users = {
        str(u.get("id")): str(u.get("username", ""))
        for u in (payload.get("includes") or {}).get("users", []) or []
        if isinstance(u, dict)
    }
    tweets = [t for raw in raw_items if (t := _to_tweet(raw, users)) is not None]
    next_token = (payload.get("meta") or {}).get("next_token")
    return tweets, str(next_token) if next_token else None


def _to_tweet(raw: Any, users: dict[str, str]) -> Tweet | None:
    if not isinstance(raw, dict) or not raw.get("id"):
        return None
    tid = str(raw["id"])
    note = raw.get("note_tweet")
    if isinstance(note, dict) and note.get("text"):
        text, entities = str(note["text"]), note.get("entities")
    else:
        text, entities = str(raw.get("text", "")), raw.get("entities")
    user = users.get(str(raw.get("author_id", "")), "")
    links = tuple(
        str(u["expanded_url"])
        for u in (entities or {}).get("urls", []) or []
        if isinstance(u, dict) and u.get("expanded_url")
    )
    replied = any(
        isinstance(r, dict) and r.get("type") == "replied_to"
        for r in raw.get("referenced_tweets", []) or []
    )
    return Tweet(
        id=tid,
        text=html.unescape(text),
        username=user,
        created_at=_parse_created_at(raw.get("created_at")),
        url=f"https://x.com/{user or 'i'}/status/{tid}",
        links=links,
        is_reply=replied,
    )


def _parse_created_at(raw: Any) -> datetime.datetime | None:
    """ "2026-09-26T10:00:00.000Z" -> naif UTC."""
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.datetime.strptime(str(raw), fmt)
        except ValueError:
            continue
    return None


def _error_summary(resp: Any) -> str:
    """Judul + detail error X (`{"title":..., "detail":...}` atau `{"errors":[...]}`),
    dipotong; kalau bukan JSON, potongan body-nya."""
    try:
        body = resp.json()
    except ValueError:
        return str(resp.text)[:200]
    if not isinstance(body, dict):
        return str(body)[:200]
    if body.get("title") or body.get("detail"):
        return f"{body.get('title', '')} -- {body.get('detail', '')}".strip(" -")[:300]
    errors = body.get("errors")
    if isinstance(errors, list) and errors and isinstance(errors[0], dict):
        return str(errors[0].get("message") or errors[0])[:300]
    return str(body)[:200]
