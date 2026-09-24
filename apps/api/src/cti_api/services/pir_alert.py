"""Port `check_new_articles_vs_pirs()` (`ScraperNewsWeb/app/services/
pir_service.py:227`) -- Fase 7.8, salah satu dari 5 loop Celery beat.

Beda desain dari versi lama yang PENTING buat dicatat: versi lama nge-
dedup alert pakai `_alerted_urls`/`_alerted_date`, dua GLOBAL MODULE-LEVEL
di proses `asyncio` yang jalan terus (satu proses uvicorn, satu loop). Itu
persis pola state in-process yang jadi salah satu ALASAN revamp ini (plan:
">1 worker gandain loop N kali") -- gak aman buat Celery beat (bisa lebih
dari satu worker, restart kapan aja, beat sendiri proses terpisah dari
worker yang eksekusi task).

Fix di sini: TANPA state persisten sama sekali. `since` (dikirim caller,
Celery task -- lihat `cti_worker.tasks.periodic`) dipakai buat filter
`Article.created_at >= since` (`AsyncPIRRepo.list_articles_for_pir`'s
`created_at_start`, BUKAN `posted_on` -- lihat docstring situ) -- selama
beat motong window PERSIS selebar interval-nya (tiap tick: `since = now -
interval`, gak overlap gak ada gap), tiap artikel ke-tangkep TEPAT SEKALI,
gak butuh set dedup terpisah.

P1 vs P2+ juga didesain ulang biar gak overlap: versi lama SATU loop
ngecek SEMUA PIR tiap tick, tapi cuma KIRIM alert P1 di tick yang bukan
"all tick" (throttle di titik KIRIM, bukan titik CEK) -- dedup-nya
mengandalkan `_alerted_urls` yang sama biar P1 gak dobel kealert di "all
tick" berikutnya. Di sini partisi di titik CEK: `only_priority="P1"`
(dipanggil tiap `pir_p1_alert_interval_min`) DAN `exclude_priority="P1"`
(dipanggil tiap `pir_alert_interval_min`, window LEBIH LEBAR) gak pernah
overlap window YANG SAMA buat PIR yang sama -- gak butuh dedup state."""

from __future__ import annotations

import datetime
from typing import Any

from cti_core.db.repositories.article import AsyncArticleRepo
from cti_core.db.repositories.pir import AsyncPIRRepo, _has_criteria
from sqlalchemy.ext.asyncio import AsyncSession

_MAX_ARTICLES_PER_PIR = 5
"""Port `.limit(5)` lama -- alert Telegram, bukan halaman list; artikel
lebih lama biarin kelihatan lewat UI, alert cuma perlu contoh secukupnya."""


async def check_new_articles_vs_pirs(
    session: AsyncSession,
    *,
    since: datetime.datetime,
    only_priority: str | None = None,
    exclude_priority: str | None = None,
) -> list[dict[str, Any]]:
    """`[{"pir": PIRRequirement, "articles": [Article, ...]}, ...]` buat
    PIR aktif yang kriterianya kena artikel baru (`created_at >= since`)
    DAN masih dalam jendela aktif (`start_date`/`end_date`) hari ini.

    PIR tanpa kriteria (match-all) DILEWATIN -- port `if not q: continue`
    lama, alert match-all bakal nembak semua artikel baru, bukan sinyal
    berguna."""
    pir_repo = AsyncPIRRepo(session)
    article_repo = AsyncArticleRepo(session)

    pirs = await pir_repo.list_active_unscoped()
    today = datetime.date.today()
    results: list[dict[str, Any]] = []

    for pir in pirs:
        if only_priority is not None and pir.priority != only_priority:
            continue
        if exclude_priority is not None and pir.priority == exclude_priority:
            continue
        if pir.end_date and today > pir.end_date:
            continue
        if pir.start_date and today < pir.start_date:
            continue
        if not _has_criteria(pir.criteria):
            continue

        articles, _total = await pir_repo.list_articles_for_pir(
            pir, article_repo, page=1, page_size=_MAX_ARTICLES_PER_PIR, created_at_start=since
        )
        if articles:
            results.append({"pir": pir, "articles": articles})

    return results


def format_pir_alert(pir: Any, articles: list[Any]) -> str:
    """Port `_format_pir_alert()` -- HTML Telegram (`parse_mode=HTML`,
    lihat `cti_alerts.telegram.send_alert`)."""
    icon = "🚨" if pir.priority == "P1" else "🔔"
    urgency = " ⚡ CRITICAL — Immediate action required" if pir.priority == "P1" else ""
    msg = f"{icon} <b>PIR MATCH — {pir.priority}{urgency}</b>\n<b>{pir.title}</b>"
    if pir.owner:
        msg += f"  |  {pir.owner}"
    msg += "\n\n"
    for a in articles:
        posted_on = a.posted_on.isoformat() if a.posted_on else ""
        msg += (
            f'• <a href="{a.url}">{a.title}</a>\n'
            f"  {a.source} · {posted_on} · {a.news_type or ''}\n\n"
        )
    return msg.strip()
