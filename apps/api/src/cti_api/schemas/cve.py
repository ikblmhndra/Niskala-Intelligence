"""Adaptasi dari `ScraperNewsWeb/app/models/cve_tracker.py`. Field CISA-
KEV/EPSS (flat: `cisa_kev`/`active_exploitation`/`epss_score`/
`epss_percentile`) SEKARANG diekspos (Fase 7.4 Grup B) -- blob deskriptif
mentah (`cisa_kev_detail`/`exploit_db_hits`) SENGAJA belum, list view
tetap ringkas, lihat docstring `cti_api.routers.cve`. Field yang nempel
fitur ticket/export/campaign SENGAJA masih gak ada di sini (lihat Grup
C/A, plan §Fase 7.4)."""

from __future__ import annotations

from pydantic import BaseModel


class CveReferenceOut(BaseModel):
    url: str


class CvePocOut(BaseModel):
    url: str
    source: str = ""
    poc_type: str = "poc"


class CveOut(BaseModel):
    id: int
    cve_id: str
    tech: str = ""
    link: str = ""
    summary: str = ""
    published: str = ""
    reference: list[CveReferenceOut] = []
    affected: list[str] = []
    solutions: str = ""
    cve_score: float = 0.0
    cve_severity: str = ""
    cvss_vector: str = ""
    last_updated: str = ""
    poc_available: bool = False
    pocs: list[CvePocOut] = []
    false_positive: bool = False
    detected_on: str = ""
    news_mentions_count: int = 0
    news_mentions: list[dict[str, str]] = []
    tech_exposure: str = "internal"
    hosting_type: str = "on_prem"
    adjusted_risk_score: float = 0.0
    cisa_kev: bool = False
    active_exploitation: bool = False
    epss_score: float | None = None
    epss_percentile: float | None = None


class CveListResponse(BaseModel):
    cves: list[CveOut]
    total: int
    page: int
    page_size: int


class CveStats(BaseModel):
    total: int
    critical: int
    high: int
    medium: int
    low: int


class BulkFalsePositiveBody(BaseModel):
    cve_ids: list[str]


class PurgeOrphanedBody(BaseModel):
    dry_run: bool = True
