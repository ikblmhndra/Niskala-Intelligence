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
    """Nulis ke `cve_tracker`. Sink dipasang pas Fase 4 nge-port
    `newCveThreat.py` (lihat `scrapers/.../feeds/new_cve.py`), sesuai
    keputusan "gak bangun lebih dulu dari kebutuhan" yang sama kayak Fase 2."""

    cve_id: str
    client_id: str
    tech: str | None = None
    link: str | None = None
    summary: str | None = None
    published: datetime.date | None = None
    cve_modified_date: datetime.date | None = None
    """Tanggal MITRE terakhir update record ini -- field DB `CveTracker`
    udah ada dari Fase 2, tapi ketinggalan di draft awal Item ini (Fase 3
    nulis "sink belum didaftarin" -- ini momen finalisasi-nya). Dipakai
    web nanti buat nunjukin CVE mana yang baru berubah, BUKAN buat
    keputusan alert (itu ranah cti-alerts, di luar scraper)."""
    references: list[str] = Field(default_factory=list)
    affected: list[str] = Field(default_factory=list)
    solutions: str | None = None
    cve_score: float | None = None
    cve_severity: str | None = None
    cvss_vector: str | None = None

    def dedup_key(self) -> str:
        return f"{self.cve_id}:{self.client_id}"


class CvePocItem(Item):
    """Nambahin SATU POC/exploit repo ke `cve_tracker.pocs` (baris yang
    `cve_id`-nya cocok, lintas client) -- MELEWATI pipeline artikel, gantiin
    `githubPOCMonitor.py`. Beda dari `CveItem`: dedup NORMAL (bukan
    di-override `None`) -- satu URL POC gak berubah lagi begitu ketemu,
    gak kayak `CveItem` yang datanya bisa di-update MITRE kapan aja."""

    cve_id: str
    url: str
    source: str = ""
    poc_type: str = "poc"
    """"poc" atau "exploit" -- klasifikasi regex sederhana (lihat scraper)."""

    def dedup_key(self) -> str:
        return f"{self.cve_id}:{self.url}"


class MalwareTrendItem(Item):
    """Nulis ke `malware_trends`, MELEWATI pipeline artikel -- gantiin
    `anyrunTrendThreat.py`. Satu Item = satu POSISI RANKING di satu HARI
    (bukan satu artikel), sesuai `dedup_key()` yang nyertain `snapshot_date`
    -- leaderboard berubah hari ke hari, disimpen sebagai time-series,
    bukan ditimpa."""

    source: str
    snapshot_date: datetime.date
    rank: int
    malware_name: str
    malware_type: str | None = None
    url: str
    report_count: str | None = None

    def dedup_key(self) -> str:
        return f"{self.source}:{self.snapshot_date}:{self.rank}"


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
