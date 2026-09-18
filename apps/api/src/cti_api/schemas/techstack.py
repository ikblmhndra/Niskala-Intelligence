"""Adaptasi dari `ScraperNewsWeb/app/models/techstack.py` -- `id` sekarang
`int`, `added_date` sekarang tanggal ISO string (bisa kosong)."""

from __future__ import annotations

from pydantic import BaseModel

EXPOSURE_MULTIPLIER = {"public": 1.5, "both": 1.25, "internal": 1.0}
HOSTING_MULTIPLIER = {"on_prem": 1.0, "cloud": 1.0, "saas": 0.8}
"""Dipakai `cve.py` (nyusul) buat `adjusted_risk_score` -- didefinisikan
di sini (bukan di router `cve.py` yang belum ada) karena ini genuinely
punya `techstack`, bukan `cve`."""


class TechStackOut(BaseModel):
    id: int
    name: str
    added_date: str = ""
    source: str = ""
    exposure: str = "internal"
    hosting_type: str = "on_prem"


class TechStackAdd(BaseModel):
    name: str
    exposure: str = "internal"
    hosting_type: str = "on_prem"


class TechStackExposureUpdate(BaseModel):
    exposure: str


class TechStackHostingUpdate(BaseModel):
    hosting_type: str


class TechStackListResponse(BaseModel):
    items: list[TechStackOut]
    total: int
    page: int
    page_size: int
