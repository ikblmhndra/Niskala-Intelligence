"""Item yang boleh di-`yield` scraper. `fetch()` gak pernah nulis DB
langsung -- dia `yield` salah satu dari ini, sink registry (sinks.py) yang
nentuin tujuannya dari TIPE-nya. Ini jalan keluar scraper bespoke tanpa
`if scraper.is_special` di mana pun: mau nulis bentuk dokumen sendiri,
`yield` tipe Item yang beda, bukan minta pengecualian ke framework.
"""

from __future__ import annotations

import datetime
from typing import Any

from cti_core.urlkit import canonicalize_url
from pydantic import BaseModel, ConfigDict, Field


class Item(BaseModel):
    """Base. Jangan dipakai langsung -- subclass ini yang di-`yield`."""

    model_config = ConfigDict(extra="forbid")

    def dedup_key(self) -> str | None:
        """Identitas stabil buat item ini. `None` artinya item ini gak
        dedup sama sekali (mis. collector snapshot penuh yang emang mau
        nulis ulang tiap kali). Framework nge-hash ini bareng scraper_id
        (lihat dedup.py) -- jangan hash sendiri di sini."""
        raise NotImplementedError


class ArticleItem(Item):
    """Item paling umum -- ~91 dari job aktif Rundeck nge-yield ini.
    Masuk pipeline enrichment (Fase 5), bukan langsung ke tabel `articles`."""

    title: str
    url: str
    posted_on: datetime.date | None = None
    summary: str | None = None
    author: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)
    """Passthrough spesifik-family -- mis. kategori RSS, field API mentah
    yang belum tentu kepake tapi sayang dibuang. Bukan tempat nulis field
    yang beneran dipakai; itu harusnya jadi field asli di atas."""

    def dedup_key(self) -> str:
        return canonicalize_url(self.url)


class RansomwareVictimItem(Item):
    """Nulis langsung ke `ransomware_victims`, MELEWATI pipeline enrichment
    artikel -- lihat sinks.py. Ini contoh kanonik "scraper bespoke", gantiin
    `ransomwareLiveThreat.py`."""

    group_name: str
    victim: str
    country_code: str = ""
    industry: str = ""
    published: datetime.date | None = None
    discovered: datetime.date | None = None
    domain: str = ""
    description: str = ""
    post_url: str = "Unknown"
    ransom: str | None = None
    data_size: str | None = None
    screenshot: str = ""

    def dedup_key(self) -> str:
        # Format WAJIB 5 bagian match persis `offset_string` di
        # ransomwareLiveThreat.py lama -- ketauan dari golden test, bukan
        # ditebak: draft pertama field ini cuma 4 bagian (lupa `industry`).
        return (
            f"{self.group_name}:{self.victim}:{self.country_code}:{self.industry}:{self.published}"
        )


class CveItem(Item):
    """Nulis ke `cve_tracker`. Sink-nya belum didaftarin di Fase 3 --
    dipasang pas Fase 4/7 nge-port `newCveThreat.py`, sesuai keputusan
    "gak bangun lebih dulu dari kebutuhan" yang sama kayak Fase 2."""

    cve_id: str
    client_id: str
    tech: str | None = None
    link: str | None = None
    summary: str | None = None
    published: datetime.date | None = None
    references: list[str] = Field(default_factory=list)
    affected: list[str] = Field(default_factory=list)
    solutions: str | None = None
    cve_score: float | None = None
    cve_severity: str | None = None
    cvss_vector: str | None = None

    def dedup_key(self) -> str:
        return f"{self.cve_id}:{self.client_id}"


class PackageVulnItem(Item):
    """Nulis ke `package_vulns`. Sink belum didaftarin -- sama alasan CveItem."""

    ecosystem: str
    package: str
    vuln_id: str
    severity: str | None = None
    epss: float | None = None
    kev: bool = False
    aliases: list[str] = Field(default_factory=list)

    def dedup_key(self) -> str:
        return f"{self.ecosystem}:{self.package}:{self.vuln_id}"
