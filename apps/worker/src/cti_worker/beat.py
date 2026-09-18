"""Beat schedule DI-GENERATE dari registry scraper (plan §4: "tiap scraper
membawa schedule-nya sendiri, tidak ada file jadwal terpusat untuk
diedit") -- BUKAN dict statis yang di-maintain manual. Tambah scraper baru
= tambah satu file di `scrapers/`, jadwalnya otomatis muncul di sini pas
beat restart, gak ada tempat lain yang perlu disentuh.

`ScraperMeta.schedule` udah cron 5-field standar (`spread()`, Fase 3,
motong field MENIT `*/N` biar N scraper gak nembak bareng) -- konversi ke
`celery.schedules.crontab` itu pemetaan LANGSUNG per-field, bukan translasi
yang perlu library tambahan."""

from __future__ import annotations

import re

from celery.schedules import crontab
from cti_scraper.registry import discover

from cti_worker.queues import queue_for

_RE_ZERO_STEP = re.compile(r"^0/(\d+)$")


def _normalize_field(field: str) -> str:
    """POSIX cron terima `0/N` ("mulai dari 0, tiap N unit", sama artinya
    `*/N` buat field APA PUN -- 0 selalu nilai minimum tiap field cron).
    Parser `celery.schedules.crontab` gak nerima bentuk `0/N`, cuma
    `*/N` -- ketauan LIVE: scraper `eset` (jadwal dipulihin dari Rundeck,
    Fase 4 `import_rundeck.py`) punya jam `"0/1"`. Ganti ke `*/N`, hasil
    match SAMA PERSIS (kedua bentuk = "tiap N unit mulai dari awal field").
    `N/M` non-zero-start (mis. "5/10") DIBIARIN apa adanya -- gak ada
    kasus itu di 83 scraper aktif sekarang, dan konversi yang bener butuh
    tau batas maksimum field ini (beda-beda per field), bukan sesuatu yang
    aman ditebak generik."""
    m = _RE_ZERO_STEP.match(field)
    return f"*/{m.group(1)}" if m else field


def _cron_to_crontab(cron: str) -> crontab:
    minute, hour, day_of_month, month_of_year, day_of_week = cron.split()
    return crontab(
        minute=_normalize_field(minute),
        hour=_normalize_field(hour),
        day_of_month=_normalize_field(day_of_month),
        month_of_year=_normalize_field(month_of_year),
        day_of_week=_normalize_field(day_of_week),
    )


def build_beat_schedule() -> dict[str, dict[str, object]]:
    schedule: dict[str, dict[str, object]] = {}
    for scraper_id, cls in discover().items():
        meta = cls.meta
        if not meta.enabled:
            continue
        schedule[f"scrape-{scraper_id}"] = {
            "task": "scrape.run",
            "schedule": _cron_to_crontab(meta.schedule),
            "args": (scraper_id,),
            "options": {"queue": queue_for(meta)},
        }
    return schedule
