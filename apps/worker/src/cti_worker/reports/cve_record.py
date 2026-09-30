"""Ringkasan CVE dari record MITRE (`cveawg.mitre.org`) buat laporan Top CVE --
port blok yang DISALIN dua kali di `topCve.py` dan `TwitterScrap/trendingCve.py`
(skor CVSS, produk/vendor terdampak, kategori, kecocokan tech stack).

Perubahan dari kode lama (semuanya perbaikan, bukan perubahan desain):
  - Skor: `metrics[].<cvssV*>.baseScore` diambil maksimumnya. Kode lama menelusuri
    `containers.cna.metrics` dan HANYA jatuh ke `adp` kalau `KeyError`; satu entri
    `other` (tanpa `baseScore`) di `cna` memicu KeyError itu secara kebetulan, dan
    `cna` yang ada tapi kosong menghasilkan skor "0". Sekarang: kumpulkan skor dari
    `cna`, kalau tidak ada coba `adp`, kalau tetap tidak ada -> None ("N/A").
  - Kecocokan tech stack pakai `re.escape` dan MELEWATI nama kosong: `re.search("",
    vendor)` di kode lama selalu cocok, jadi satu baris kosong di techstack.txt
    menandai SEMUA CVE "Might Applicable to Organization!".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import httpx

MITRE_URL = "https://cveawg.mitre.org/api/cve"
_MISSING_MESSAGE = "The cve record for the cve id does not exist."
_SKIP_METRIC_KEYS = {"scenarios", "format", "other"}
_SEP = " || "


@dataclass(frozen=True)
class CveSummary:
    cve_id: str
    base_score: float | None
    category: str
    product: str
    vendor: str
    applicable: bool

    @property
    def score_text(self) -> str:
        return "N/A" if self.base_score is None else f"{self.base_score:g}"


def score_category(score: float | None) -> str:
    if score is None:
        return "None"
    if 0.13 <= score <= 3.9:
        return "Low"
    if 4.0 <= score <= 6.9:
        return "Medium"
    if 7.0 <= score <= 8.9:
        return "High"
    if score >= 9.0:
        return "Critical"
    return "None"


def _scores(metrics: Any) -> list[float]:
    found: list[float] = []
    for entry in metrics if isinstance(metrics, list) else []:
        for key, value in entry.items() if isinstance(entry, dict) else []:
            if key in _SKIP_METRIC_KEYS or not isinstance(value, dict):
                continue
            score = value.get("baseScore")
            if isinstance(score, int | float):
                found.append(float(score))
    return found


def base_score(record: dict[str, Any]) -> float | None:
    containers = record.get("containers", {}) if isinstance(record, dict) else {}
    cna = containers.get("cna", {})
    cna_scores = _scores(cna.get("metrics") if isinstance(cna, dict) else None)
    if cna_scores:
        return max(cna_scores)
    adp_scores = [s for adp in _dicts(containers.get("adp")) for s in _scores(adp.get("metrics"))]
    return max(adp_scores) if adp_scores else None


def _dicts(value: Any) -> list[dict[str, Any]]:
    """Record MITRE dari CNA mana pun kadang berbentuk aneh -- ambil cuma elemen dict."""
    return [v for v in value if isinstance(v, dict)] if isinstance(value, list) else []


def _affected_products(affected_list: Any, seen: list[str]) -> list[str]:
    names: list[str] = []
    for affected in _dicts(affected_list):
        product = affected.get("product", "")
        low = str(product).lower()
        for version in _dicts(affected.get("versions")):
            if version.get("status") == "affected" and low not in seen and low != "n/a":
                names.append(str(product))
                seen.append(low)
    return names


def product_vendor(record: dict[str, Any]) -> tuple[str, str]:
    containers = record.get("containers", {}) if isinstance(record, dict) else {}
    seen: list[str] = []
    products: list[str] = []
    vendor = ""

    for adp in _dicts(containers.get("adp")):
        products += _affected_products(adp.get("affected"), seen)
        for affected in _dicts(adp.get("affected")):
            if _dicts(affected.get("versions")):
                vendor = str(affected.get("vendor", "")).lower()

    cna = containers.get("cna", {})
    cna_affected = cna.get("affected") if isinstance(cna, dict) else None
    products += _affected_products(cna_affected, seen)
    for affected in _dicts(cna_affected):
        if _dicts(affected.get("versions")) and (not vendor or vendor == "n/a"):
            vendor = str(affected.get("vendor", ""))

    if not products and not vendor:
        return "Unknown", "Unknown"
    return _SEP.join(products), vendor


def applicable_to_stack(vendor: str, techstack: list[str]) -> bool:
    v = vendor.lower()
    return any(t.strip() and re.search(re.escape(t.strip().lower()), v) for t in techstack)


def summarize(cve_id: str, record: dict[str, Any], techstack: list[str]) -> CveSummary:
    score = base_score(record)
    product, vendor = product_vendor(record)
    return CveSummary(
        cve_id=cve_id.upper(),
        base_score=score,
        category=score_category(score),
        product=product,
        vendor=vendor,
        applicable=applicable_to_stack(vendor, techstack),
    )


def fetch_record(client: httpx.Client, cve_id: str) -> dict[str, Any] | None:
    """Record MITRE, atau `None` kalau CVE-nya tidak ada / responsnya tidak bisa
    dibaca (CVE yang belum dipublikasikan sering muncul di tweet)."""
    try:
        resp = client.get(f"{MITRE_URL}/{cve_id.upper()}", timeout=30)
        record = resp.json()
    except (httpx.HTTPError, ValueError):
        return None
    if not isinstance(record, dict) or record.get("message") == _MISSING_MESSAGE:
        return None
    if resp.status_code != 200:
        return None
    return record
