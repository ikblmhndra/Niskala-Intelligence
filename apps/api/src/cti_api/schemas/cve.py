"""Adaptasi dari `ScraperNewsWeb/app/models/cve_tracker.py` -- field yang
nempel fitur DITUNDA (ticket/CISA-KEV/exploit-db/EPSS/newsletter) SENGAJA
gak ada di sini, bukan kelewat. Lihat docstring `cti_api.routers.cve`."""

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
