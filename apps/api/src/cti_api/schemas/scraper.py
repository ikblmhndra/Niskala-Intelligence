"""Fase 9 -- control plane scraper. Skema BARU (bukan port dari legacy,
survei Fase 8 udah nyimpulin `scraper.js` bukan control plane beneran).
Semua timestamp `str` ISO 8601 -- pola sama kayak router lain di sini
(`newsletter.py`/`recap.py` dst), bukan `datetime` biar frontend gak perlu
parse ulang, cukup tampilin apa adanya."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ScraperConfigOut(BaseModel):
    """`None` di tiap field override = "gak ada override, pakai default
    kode" -- `enabled` kekecualian (selalu bool efektif, gabungan
    `ScraperConfig.enabled` kalau ada baris override, else `ScraperMeta.
    enabled` kode)."""

    enabled: bool
    schedule: str | None
    rate_limit: str | None
    max_items: int | None
    paused_reason: str | None
    updated_by: str | None
    updated_at: str | None


class ScraperListItem(BaseModel):
    id: str
    source: str
    runtime: str
    queue: str
    tags: list[str]
    enabled: bool
    """Efektif -- `ScraperConfig.enabled` kalau ada override, else
    `ScraperMeta.enabled` kode."""
    schedule: str
    """Efektif -- `ScraperConfig.schedule` kalau ada override, else
    `ScraperMeta.schedule` kode. INGAT: override baru kepake abis beat
    restart, lihat docstring `cti_worker.beat`."""
    has_override: bool
    last_run_id: str | None
    last_status: str | None
    last_trigger: str | None
    last_started_at: str | None
    last_finished_at: str | None
    last_items_found: int | None
    last_items_new: int | None


class ScraperListResponse(BaseModel):
    scrapers: list[ScraperListItem]
    total: int


class ScraperDetail(BaseModel):
    id: str
    source: str
    runtime: str
    credential: str | None
    reference_data: list[str]
    tags: list[str]
    notes: str
    default_schedule: str
    default_rate_limit: str
    default_max_items: int
    default_enabled: bool
    default_timeout_s: float
    default_max_retries: int
    default_dedup_ttl_days: int
    queue: str
    config: ScraperConfigOut


class ScraperRunOut(BaseModel):
    run_id: str
    scraper_id: str
    trigger: str
    status: str
    started_at: str
    finished_at: str | None
    duration_ms: int | None
    items_found: int
    items_new: int
    items_dropped: int
    items_failed: int
    errors: list[dict[str, Any]]
    celery_task_id: str | None


class ScraperRunListResponse(BaseModel):
    runs: list[ScraperRunOut]
    total: int
    page: int
    page_size: int


class ScraperItemOut(BaseModel):
    id: int
    run_id: str
    title: str
    url: str
    accepted: bool
    reason: str | None
    run_at: str


class ScraperItemListResponse(BaseModel):
    items: list[ScraperItemOut]
    total: int
    page: int
    page_size: int


class ScraperTriggerResult(BaseModel):
    scraper_id: str
    celery_task_id: str
    trigger: str
    queue: str


class ScraperDryRunResult(BaseModel):
    scraper_id: str
    status: str
    items_found: int
    duration_ms: int
    errors: list[dict[str, Any]]


class ScraperConfigUpdateBody(BaseModel):
    """PATCH-style -- field yang gak dikirim (bukan dikirim `null`) gak
    disentuh, lihat `ScraperConfigRepo.upsert()`'s sentinel `UNSET`.
    Router baca `body.model_fields_set` buat mbedain "gak dikirim" dari
    "dikirim null", bukan dari nilai field ini sendiri."""

    schedule: str | None = None
    rate_limit: str | None = None
    max_items: int | None = None
    paused_reason: str | None = None


class ScraperDisableBody(BaseModel):
    reason: str | None = None


class ScraperResetDedupResult(BaseModel):
    scraper_id: str
    deleted: int


class ScraperHealthEntryOut(BaseModel):
    id: str
    source: str
    status: str
    """ok | disabled | stale | dead | degraded | zero_yield -- lihat
    `cti_scraper.health.HealthStatus`."""
    last_status: str | None
    last_started_at: str | None


class ScraperHealthSummary(BaseModel):
    generated_at: str
    counts: dict[str, int]
    """Key = `HealthStatus`, cuma status yang beneran muncul (gak semua
    6 selalu ada)."""
    problems: list[ScraperHealthEntryOut]
    """Subset non-`ok` (dan non-`disabled` -- itu bukan masalah, operator
    yang minta) -- ini yang dashboard/digest peduliin, bukan 84 baris
    penuh tiap kali."""
