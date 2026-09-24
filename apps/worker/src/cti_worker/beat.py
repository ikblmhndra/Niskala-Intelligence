"""Beat schedule DI-GENERATE dari registry scraper (plan §4: "tiap scraper
membawa schedule-nya sendiri, tidak ada file jadwal terpusat untuk
diedit") -- BUKAN dict statis yang di-maintain manual. Tambah scraper baru
= tambah satu file di `scrapers/`, jadwalnya otomatis muncul di sini pas
beat restart, gak ada tempat lain yang perlu disentuh.

`ScraperMeta.schedule` udah cron 5-field standar (`spread()`, Fase 3,
motong field MENIT `*/N` biar N scraper gak nembak bareng) -- konversi ke
`celery.schedules.crontab` itu pemetaan LANGSUNG per-field, bukan translasi
yang perlu library tambahan.

6 entri statis di `_PERIODIC_SCHEDULE` (Fase 7.8, `tasks/periodic.py`) --
port 5 loop `ScraperNewsWeb/app/main.py`. Jam IOC decay (04:00)/daily
recap (06:00)/CVE enrichment (tiap 3 jam) HARDCODED port apa adanya dari
`_seconds_until_04h_utc()`/`_seconds_until_06h_utc()`/
`_seconds_until_next_3h()` lama (gak pernah env-configurable di kode
lama, jadi gak dijadiin `Settings` field juga di sini). PIR
P1/all-interval PAKAI `Settings.worker` (lihat docstring
`cti_api.services.pir_alert` soal kenapa dipecah 2 entry) -- BUKAN
`get_settings()` dipanggil pas modul ini di-import (`build_beat_schedule()`
dipanggil sekali di `celery_app.py`, env harus udah siap saat itu, sama
kayak semua env lain yang dibaca modul ini)."""

from __future__ import annotations

import re

from celery.schedules import crontab
from cti_core.config import get_settings
from cti_scraper.registry import discover

from cti_worker.queues import QUEUE_MAINTENANCE, QUEUE_NOTIFY, queue_for

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


def _periodic_schedule() -> dict[str, dict[str, object]]:
    w = get_settings().worker
    return {
        "pir-check-p1-alerts": {
            "task": "pir.check_p1_alerts",
            "schedule": crontab(minute=f"*/{w.pir_p1_alert_interval_min}"),
            "options": {"queue": QUEUE_NOTIFY},
        },
        "pir-check-all-alerts": {
            "task": "pir.check_all_alerts",
            "schedule": crontab(minute=f"*/{w.pir_alert_interval_min}"),
            "options": {"queue": QUEUE_NOTIFY},
        },
        "attack-sync-check": {
            "task": "attack.sync_check",
            "schedule": crontab(hour=5, minute=0),
            "options": {"queue": QUEUE_MAINTENANCE},
        },
        "ioc-decay-sweep": {
            "task": "ioc.decay_sweep",
            "schedule": crontab(hour=4, minute=0),
            "options": {"queue": QUEUE_MAINTENANCE},
        },
        "recap-generate-daily": {
            "task": "recap.generate_daily",
            "schedule": crontab(hour=6, minute=0),
            "options": {"queue": QUEUE_MAINTENANCE},
        },
        "cve-enrichment-sweep": {
            "task": "cve.enrichment_sweep",
            "schedule": crontab(hour="*/3", minute=0),
            "options": {"queue": QUEUE_MAINTENANCE},
        },
    }


def build_beat_schedule() -> dict[str, dict[str, object]]:
    schedule: dict[str, dict[str, object]] = dict(_periodic_schedule())
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
