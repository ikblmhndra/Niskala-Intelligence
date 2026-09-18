"""monitorX -- BESPOKE, subclass `BaseScraper` langsung. Nge-`yield`
`TweetItem` (Fase 5) per tweet dari akun yang dipantau
(`monitored_accounts`, `credential="twitter"` lewat twitterapi.io), gantiin
`ScraperNews/monitorX.py`.

Bandingkan sama script lama:
- Auth twitterapi.io lewat header manual `X-API-Key` + `cfg['twitter']
  ['api_key']` -- di sini `meta.credential="twitter"` (Fase 4), scraper gak
  pernah pegang key-nya sendiri.
- Regex scan (`_scan_tweet`, `nlp.py:33-90 dan monitorX.py:95-127` --
  DUA salinan PERSIS keyword list yang sama) -- di sini
  `cti_enrich.stages.score.score_with_lists()` (Fase 5, SATU implementasi).
  Dipanggil `title=text, body=""` -- `_scan_tweet` lama emang single-pass
  (gak ada NER, gak import spacy sama sekali), setara title-pass `score()`.
  Efek samping konsolidasi: regex zero-day di sini ikut FIX bareng
  `nlp.py:421` (score.py pakai versi bener), padahal monitorX.py PUNYA regex
  zero-day sendiri yang beda lagi (`r"(zero|0).day"`, tanpa `\b`, titik-bukan-
  literal) -- bukan bug yang sama, tapi ilang begitu SATU implementasi dipakai.
- Validasi LLM (`articleValidator(text)`) -- di sini
  `cti_enrich.stages.classify.classify(text)` (Fase 5, SATU LLM client +
  fix `response_format`).
- `state.json` (`load_state`/`save_state`, file lokal per-proses) -- gantiin
  `reference_data="tweet_last_seen_ids"` (MAX tweet_id per akun dari
  Postgres, di-resolve Runner SEBELUM `fetch()` -- state gak ilang kalau
  container di-restart, beda dari file lokal).
- Lockfile `/tmp/monitorX.lock` (cegah concurrent cron run) -- gak
  dibutuhin, `Runner` (Fase 3) udah nolak run konkuren per `scraper_id`
  lewat mekanisme sendiri.
- `time.sleep(5)`/`time.sleep(1)` manual antar-request -- `meta.rate_limit`
  (token bucket per-domain, Fase 3) yang urus, bukan sleep hardcode.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta
from typing import Any

from cti_enrich.stages.classify import ClassifyResult, OpenAIQuotaExhausted, classify
from cti_enrich.stages.score import ScoreResult, score_with_lists
from cti_scraper.base import BaseScraper, ScrapeContext, ScraperMeta
from cti_scraper.items import TweetItem
from cti_scraper.schedule import spread

_SEARCH_URL = "https://api.twitterapi.io/twitter/tweet/advanced_search"
_MAX_PAGES_PER_ACCOUNT = 3
_FIRST_RUN_WINDOW = timedelta(hours=3)


def _parse_created_at(raw: str) -> datetime | None:
    # "Mon May 11 13:00:57 +0000 2026"
    try:
        return datetime.strptime(raw, "%a %b %d %H:%M:%S +0000 %Y")
    except ValueError:
        return None


def _fetch_tweets_for_account(
    ctx: ScrapeContext, account: str, since_id: str | None
) -> list[dict[str, Any]]:
    query = f"from:{account} -is:retweet -filter:replies"
    if since_id:
        query += f" since_id:{since_id}"
    else:
        since_time = ctx.now - _FIRST_RUN_WINDOW
        query += f" since_time:{int(since_time.timestamp())}"

    params: dict[str, str] = {"query": query, "queryType": "Latest"}
    all_tweets: list[dict[str, Any]] = []
    next_cursor: str | None = None

    for _page in range(_MAX_PAGES_PER_ACCOUNT):
        if next_cursor:
            params["cursor"] = next_cursor
        resp = ctx.http.get(_SEARCH_URL, params=params)
        if resp.status_code != 200:
            # Port cek eksplisit `monitorX.py:280-281` -- `ScraperHttpClient`
            # gak auto-raise di 4xx (cuma 429/5xx, lihat http.py), dan
            # twitterapi.io balikin 401/dst dengan body `{"error": ...}`
            # yang KALAU gak dicek bakal ke-`.get("tweets", [])` jadi `[]`
            # diam-diam -- auth invalid keliatan kayak "gak ada tweet baru".
            ctx.log.warning(
                "monitor_x: API error",
                account=account,
                status=resp.status_code,
                body=resp.text[:200],
            )
            break
        data = resp.json()
        tweets = data.get("tweets", [])
        if tweets:
            all_tweets.extend(tweets)
        if data.get("has_next_page") and data.get("next_cursor"):
            next_cursor = data["next_cursor"]
        else:
            break

    return all_tweets


def _build_tweet_item(
    tweet: dict[str, Any], scan: ScoreResult, llm: ClassifyResult | None
) -> TweetItem:
    author = tweet.get("author", {})
    media_urls = [
        m["media_url_https"]
        for m in tweet.get("extendedEntities", {}).get("media", [])
        if m.get("media_url_https")
    ]
    apac_indicator = bool(scan.mentioned_countries or scan.mentioned_apac_people)
    scan_results = {
        "apac_indicator": apac_indicator,
        "mentioned_group": scan.mentioned_group,
        "mentioned_apac_country": scan.mentioned_countries,
        "mentioned_apac_people": scan.mentioned_apac_people,
        "cve_list": scan.cve_list_title,
        "zero_day_list": scan.zero_day_list,
        "databreach_list": scan.databreach_list,
        "ot_status": scan.ot_status,
        "report_status": scan.report_status,
    }
    return TweetItem(
        tweet_id=str(tweet["id"]),
        url=tweet.get("url", ""),
        text=tweet.get("text", ""),
        author_username=author.get("userName", ""),
        author_name=author.get("name"),
        author_avatar=author.get("profilePicture"),
        author_followers=int(author.get("followers", 0) or 0),
        posted_on=_parse_created_at(tweet.get("createdAt", "")),
        lang=tweet.get("lang", "en"),
        media_urls=media_urls,
        scan_results=scan_results,
        confidence_score=(round(llm.confidence * 100) if llm and llm.confidence else None),
        confirmed_incident=bool(llm.confirmed_incident) if llm else False,
        industries_impacted=llm.industries_impacted if llm else [],
        victim_countries=llm.victim_countries if llm else [],
        actor_countries=llm.actor_countries if llm else [],
        victim_name=llm.victim_name if llm else None,
        incident_confidence=(
            round(llm.incident_confidence * 100)
            if llm and llm.incident_confidence is not None
            else None
        ),
        incident_indicators=llm.incident_indicators if llm else [],
    )


class MonitorX(BaseScraper):
    meta = ScraperMeta(
        id="monitor_x",
        source="X/Twitter Intel Monitor",
        schedule=spread("*/15 * * * *", "monitor_x"),
        rate_limit="15/minute",
        max_items=200,
        credential="twitter",
        reference_data=(
            "monitored_accounts",
            "tweet_last_seen_ids",
            "techstack",
            "threat_actor_groups",
            "monitored_people",
        ),
        tags=("migrated", "bespoke"),
        legacy_label=None,  # monitorX lama gak pernah push_job/label Telegram khusus
        legacy_script="monitorX",
    )

    def fetch(self, ctx: ScrapeContext) -> Iterator[TweetItem]:
        accounts: list[str] = ctx.reference["monitored_accounts"]
        if not accounts:
            ctx.log.warning("monitor_x: gak ada monitored_accounts aktif, skip run")
            return

        last_seen: dict[str, str] = ctx.reference["tweet_last_seen_ids"]
        techstack: list[str] = ctx.reference["techstack"]
        group_list: list[str] = ctx.reference["threat_actor_groups"]
        apac_people_list: list[str] = ctx.reference["monitored_people"]

        found = 0
        for account in accounts:
            if found >= self.meta.max_items:
                return

            raw_tweets = _fetch_tweets_for_account(ctx, account, last_seen.get(account))
            raw_tweets.sort(key=lambda t: int(t["id"]))

            for tweet in raw_tweets:
                if found >= self.meta.max_items:
                    return

                text = tweet.get("text", "")
                scan = score_with_lists(
                    title=text,
                    body="",
                    techstack=techstack,
                    group_list=group_list,
                    apac_people_list=apac_people_list,
                )
                if scan.funding_keyword:
                    continue  # noise pendanaan, bukan sinyal TI -- port funding_status lama

                try:
                    llm = classify(text)
                except OpenAIQuotaExhausted:
                    raise
                except Exception:
                    ctx.log.warning(
                        "monitor_x: classify() gagal, simpan tanpa LLM", tweet_id=tweet.get("id")
                    )
                    llm = None

                if llm is not None and llm.related_cyber is False:
                    continue

                found += 1
                yield _build_tweet_item(tweet, scan, llm)
