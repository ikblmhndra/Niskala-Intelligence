"""Port `cluster_service.py`'s `get_clusters()`/`_compute_clusters()` --
Pipeline 1 dari "mesin cluster" (Fase 7.4 Grup A, 2026-09-23). TF-IDF
GREEDY clustering (fixed-centroid, threshold tunable via query param),
DI-PERSIST ke tabel `clusters` (`AsyncClusterRepo`) -- backing
`GET /api/clusters` + `/clusters/evolution` + `/clusters/{id}/trends`
(dua terakhir baca hasil persist ini, lihat `cti_api.services.
campaign_trend`).

**BEDA dari Pipeline 2** (`cti_api.services.campaign.get_recent_
campaigns()`, union-find, threshold beda, NOL persist) -- dua pipeline
independen yang kebetulan sama-sama TF-IDF, bukan satu fungsi. Lihat
docstring `Cluster` model.

TF-IDF vectorization + greedy clustering loop (keduanya CPU-bound, gak
ada `await` di dalamnya) dibungkus SATU `asyncio.to_thread()` -- legacy
manggil sklearn LANGSUNG di dalam `async def` tanpa executor sama
sekali (blocking event loop tiap request), port di sini nambahin
`to_thread` konsisten sama pola established sesi ini (`dedup_service`
Grup D, LLM calls Grup C) -- gak ngubah HASIL, cuma concurrency."""

from __future__ import annotations

import asyncio
import datetime
import re
import time
from typing import Any

from cti_core.db.repositories.article import AsyncArticleRepo
from cti_core.db.repositories.cluster import AsyncClusterRepo
from cti_core.db.repositories.source_reliability import AsyncSourceReliabilityRepo
from cti_core.db.repositories.ta import AsyncTARepo
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.ext.asyncio import AsyncSession

from cti_api.services.cluster_tokenize import (
    cluster_id,
    confidence_label,
    derive_cluster_name,
    jaccard,
    tfidf_tokenize,
    tokenize_for_dedup,
)

_CACHE: dict[tuple[int, float, bool], tuple[list[dict[str, Any]], float]] = {}
_CACHE_TTL = 900.0


def _article_ta_names(title: str, ta_names: list[str]) -> frozenset[str]:
    title_lower = title.lower()
    return frozenset(name for name in ta_names if name in title_lower)


async def get_clusters(
    session: AsyncSession,
    *,
    days: int = 30,
    threshold: float = 0.35,
    exclude_low_reliability: bool = False,
) -> list[dict[str, Any]]:
    cache_key = (days, threshold, exclude_low_reliability)
    now = time.monotonic()
    cached = _CACHE.get(cache_key)
    if cached is not None and (now - cached[1]) < _CACHE_TTL:
        return cached[0]

    result = await _compute_clusters(session, days, threshold, exclude_low_reliability)
    _CACHE[cache_key] = (result, now)
    return result


async def _compute_clusters(
    session: AsyncSession,
    days: int,
    threshold: float,
    exclude_low_reliability: bool,
) -> list[dict[str, Any]]:
    cutoff = datetime.date.today() - datetime.timedelta(days=days)
    articles, _total = await AsyncArticleRepo(session).list_filtered(
        posted_on_start=cutoff, page=1, page_size=1000
    )
    raw = [
        {
            "id": a.id,
            "title": a.title,
            "url": a.url,
            "source": a.source,
            "posted_on": a.posted_on.isoformat() if a.posted_on else "",
        }
        for a in articles
    ]

    ta_names = await AsyncTARepo(session).list_all_names()
    low_rel_sources: set[str] = set()
    if exclude_low_reliability:
        sr_repo = AsyncSourceReliabilityRepo(session)
        low_rel_sources = await sr_repo.list_low_reliability_source_names()

    result = await asyncio.to_thread(
        _cluster_articles, raw, threshold, exclude_low_reliability, ta_names, low_rel_sources
    )

    if result:
        today = datetime.date.today()
        await AsyncClusterRepo(session).upsert_and_tag(result, today=today)
        await session.commit()

    return result


def _cluster_articles(
    articles: list[dict[str, Any]],
    threshold: float,
    exclude_low_reliability: bool,
    ta_names: list[str],
    low_rel_sources: set[str],
) -> list[dict[str, Any]]:
    """CPU-bound murni -- dijalanin lewat `asyncio.to_thread`. Port
    `_compute_clusters()`'s dedup passes + TF-IDF + greedy clustering
    loop, TANPA I/O (semua data udah di-fetch caller)."""
    # ── Pass 1: exact (title, date) dedup ────────────────────────────────
    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for a in articles:
        key = (re.sub(r"\s+", " ", a.get("title", "")).strip().lower(), a.get("posted_on", ""))
        if key not in seen:
            seen.add(key)
            deduped.append(a)
    articles = deduped

    # ── Pass 2: fuzzy title dedup (Jaccard > 0.85, dates <= 2 days apart) ─
    def _parse_date(s: str) -> datetime.datetime | None:
        try:
            return datetime.datetime.strptime(s, "%Y-%m-%d")
        except (ValueError, TypeError):
            return None

    tok_cache = [tokenize_for_dedup(a.get("title", "")) for a in articles]
    date_cache = [_parse_date(a.get("posted_on", "")) for a in articles]

    fuzzy_dupes: set[int] = set()
    for i in range(len(articles)):
        if i in fuzzy_dupes:
            continue
        di = date_cache[i]
        ti = tok_cache[i]
        for j in range(i + 1, len(articles)):
            if j in fuzzy_dupes:
                continue
            dj = date_cache[j]
            if di and dj and (di - dj).days > 2:
                break
            if jaccard(ti, tok_cache[j]) > 0.85:
                fuzzy_dupes.add(j)

    articles = [a for idx, a in enumerate(articles) if idx not in fuzzy_dupes]

    if len(articles) < 2:
        return []

    # ── TF-IDF vectorization ──────────────────────────────────────────────
    titles = [a.get("title", "") for a in articles]
    vectorizer = TfidfVectorizer(
        tokenizer=tfidf_tokenize, token_pattern=None, lowercase=False, min_df=1
    )
    try:
        tfidf_matrix = vectorizer.fit_transform(titles)
    except ValueError:
        return []

    article_ta_sets = [_article_ta_names(a.get("title", ""), ta_names) for a in articles]

    # ── Greedy TF-IDF clustering with fixed-centroid logic ────────────────
    clusters: list[dict[str, Any]] = []

    for idx, (article, ta_set) in enumerate(zip(articles, article_ta_sets, strict=True)):
        article_vec = tfidf_matrix[idx]
        is_low_rel = (
            exclude_low_reliability and article.get("source", "").lower() in low_rel_sources
        )

        best_cluster = None
        best_sim = -1.0
        ta_forced = False

        for cluster in clusters:
            ta_overlap = bool(ta_set and cluster["ta_names"] and ta_set & cluster["ta_names"])

            compare_vec = (
                cluster["sum_vec"] / cluster["count"]
                if cluster["count"] >= 3
                else cluster["centroid_vec"]
            )
            sim = float(cosine_similarity(article_vec, compare_vec)[0, 0])

            if ta_overlap:
                effective = max(sim, threshold + 0.01)
                if not ta_forced or effective > best_sim:
                    best_sim = effective
                    best_cluster = cluster
                    ta_forced = True
            elif not ta_forced and sim >= threshold and sim > best_sim:
                best_sim = sim
                best_cluster = cluster

        if best_cluster:
            best_cluster["articles"].append(article)
            best_cluster["sum_vec"] = best_cluster["sum_vec"] + article_vec
            best_cluster["count"] += 1
            best_cluster["ta_names"] |= ta_set
        elif not is_low_rel:
            clusters.append(
                {
                    "centroid_vec": article_vec,
                    "sum_vec": article_vec.copy(),
                    "count": 1,
                    "ta_names": set(ta_set),
                    "articles": [article],
                }
            )

    # ── Build result ──────────────────────────────────────────────────────
    result = []
    for cluster in clusters:
        arts = cluster["articles"]
        if len(arts) < 2:
            continue
        sources = list({a["source"] for a in arts if a.get("source")})
        sorted_arts = sorted(arts, key=lambda x: x.get("posted_on", ""), reverse=True)
        dates = [a.get("posted_on", "") for a in sorted_arts if a.get("posted_on")]
        cname = derive_cluster_name([a["title"] for a in sorted_arts])
        result.append(
            {
                "cluster_id": cluster_id(cname),
                "cluster_name": cname,
                "article_count": len(arts),
                "source_count": len(sources),
                "sources": sources,
                "confidence": confidence_label(len(sources)),
                "first_date": dates[-1] if dates else "",
                "last_date": dates[0] if dates else "",
                "re_emerged": False,  # populated by AsyncClusterRepo.upsert_and_tag
                "articles": [
                    {
                        "id": a["id"],
                        "title": a.get("title", ""),
                        "url": a.get("url", ""),
                        "source": a.get("source", ""),
                        "posted_on": a.get("posted_on", ""),
                    }
                    for a in sorted_arts
                ],
            }
        )

    result.sort(key=lambda x: (x["source_count"], x["article_count"]), reverse=True)
    return result[:100]
