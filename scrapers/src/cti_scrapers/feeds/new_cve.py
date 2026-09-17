"""CVE Tracker (NVD + Tenable + MITRE) -- BESPOKE, subclass `BaseScraper`
langsung. Nge-`yield` `CveItem` per (CVE, client) pasangan -- satu CVE bisa
relevan buat lebih dari satu client (lihat `reference_data="techstack_by_client"`).

Bandingkan sama `ScraperNews/newCveThreat.py` asli (391 baris):
- Bikin `MongoClient` LANGSUNG dari config buat preload state dedup DAN
  buat baca techstack -- dua-duanya kelas bug yang `ScrapeContext` sengaja
  cegah sekarang (lihat docstring-nya). Techstack sekarang lewat
  `ctx.reference` (`Runner` yang query, `fetch()` cuma baca data jadi).
- NVD API key gak PERNAH kepake di script lama (field-nya ada di config,
  tapi gak ada satu pun `apiKey` di header/query) -- rate limit publik
  5 req/30dtk. Di sini `meta.credential="nvd"` beneran masang header
  `apiKey`, naik ke 50 req/30dtk.
- `time.sleep(10)`/`time.sleep(15)` manual antar request -- gak
  dibutuhin lagi, `meta.rate_limit` (token bucket per-domain) udah
  nanganin throttle-nya.
- Dedup `is_new_and_mark`-style DIGANTI: `dedup_key()` di-override return
  `None` (skip dedup framework sepenuhnya) -- CVE HARUS di-upsert ulang
  tiap run walau udah pernah keliatan, karena MITRE bisa update skor/
  referensi/affected-version-nya kapan aja. Script lama juga selalu upsert
  ulang (cuma skip ALERT-nya kalau `cve_modified_date` gak berubah, dan
  alert itu di luar scope scraper -- lihat cti-alerts, belum dibangun).
- **Bug lama gak ikut di-port**: `severity_string` di skrip asli di-set
  DI DALAM loop metrics, gak di-reset di awal tiap CVE -- kalau CVE
  berikutnya punya `metrics` list KOSONG (bukan KeyError, jadi gak
  ke-`except`), `severity_string` bocor bawa nilai dari CVE SEBELUMNYA.
  Di sini `severity` selalu direset `None` per kandidat.
- Telegram alert + email (`cveEmailAutomation`) -- BUKAN tanggung jawab
  scraper, itu ranah `cti-alerts` (belum dibangun).
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import date, timedelta
from typing import Any

import lxml.html
from cti_scraper.base import BaseScraper, ScrapeContext, ScraperMeta
from cti_scraper.errors import ParseError
from cti_scraper.items import CveItem, Item
from cti_scraper.schedule import spread

_NVD_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
_TENABLE_URL = "https://www.tenable.com/cve/search"
_MITRE_URL = "https://cveawg.mitre.org/api/cve"


def _mitre_date(raw: str | None) -> date | None:
    if not raw or len(raw) < 10:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


class NewCve(BaseScraper):
    meta = ScraperMeta(
        id="new_cve",
        source="NVD/Tenable CVE Tracker",
        schedule=spread("0 * * * *", "new_cve"),
        rate_limit="60/minute",
        max_items=300,  # fan-out per client bisa ngalahin 50 default gampang
        credential="nvd",
        reference_data=("techstack", "techstack_by_client"),
        tags=("migrated", "bespoke", "cve"),
        legacy_label="NEW CVE",
        legacy_script="newCveThreat",
    )

    def dedup_key(self, item: Item) -> str | None:
        """Selalu upsert ulang -- lihat penjelasan di docstring modul."""
        return None

    def fetch(self, ctx: ScrapeContext) -> Iterator[CveItem]:
        tech_list: list[str] = ctx.reference["techstack"]
        tech_by_client: dict[str, list[str]] = ctx.reference["techstack_by_client"]
        if not tech_list:
            return

        tech_to_clients: dict[str, list[str]] = {}
        for client_id, techs in tech_by_client.items():
            for tech in techs:
                tech_to_clients.setdefault(tech, []).append(client_id)

        seen_cve_ids: set[str] = set()
        candidates = [
            *self._nvd_candidates(ctx, tech_list, seen_cve_ids),
            *self._tenable_candidates(ctx, tech_list, seen_cve_ids),
        ]

        found = 0
        for cand in candidates:
            if found >= self.meta.max_items:
                return

            client_ids = tech_to_clients.get(cand["tech"])
            if not client_ids:
                ctx.log.warning(
                    "cve_candidate_no_client_match", tech=cand["tech"], cve_id=cand["id"]
                )
                continue

            detail = self._mitre_detail(ctx, cand)
            if detail is None:
                continue

            for client_id in client_ids:
                if found >= self.meta.max_items:
                    return
                found += 1
                yield CveItem(client_id=client_id, **detail)

    def _nvd_candidates(
        self, ctx: ScrapeContext, tech_list: list[str], seen: set[str]
    ) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        now_str = ctx.now.strftime("%Y-%m-%dT%H:%M:%S.000")
        start_str = (ctx.now - timedelta(days=8)).strftime("%Y-%m-%dT%H:%M:%S.000")

        for tech in tech_list:
            tech_enc = tech.replace(" ", "%20").strip()
            url = (
                f"{_NVD_URL}?keywordSearch={tech_enc}"
                f"&pubStartDate={start_str}%2B07:00&pubEndDate={now_str}%2B07:00"
            )
            data = ctx.http.get(url).json()

            for cve in data.get("vulnerabilities", []):
                cve_id = cve["cve"]["id"]
                if cve_id in seen:
                    continue
                seen.add(cve_id)
                summary = next(
                    (d["value"] for d in cve["cve"].get("descriptions", []) if d["lang"] == "en"),
                    "",
                )
                out.append(
                    {
                        "tech": tech_enc,
                        "id": cve_id,
                        "link": f"https://nvd.nist.gov/vuln/detail/{cve_id}",
                        "summary": summary,
                    }
                )
        return out

    def _tenable_candidates(
        self, ctx: ScrapeContext, tech_list: list[str], seen: set[str]
    ) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        now_str = ctx.now.strftime("%Y-%m-%d")
        start_str = (ctx.now - timedelta(days=8)).strftime("%Y-%m-%d")

        for tech in tech_list:
            tech_enc = tech.replace(" ", "+").strip()
            url = (
                f"{_TENABLE_URL}?q={tech_enc}+AND+publication_date%3A"
                f"%28%5B{start_str}+TO+{now_str}%5D%29&sort=newest&page=1"
            )
            resp = ctx.http.get(url)
            tree = lxml.html.fromstring(resp.content)

            for i in range(1, 7):
                row = (
                    "/html/body/div/div/div[2]/div/div/div[2]/div/div/div[3]"
                    f"/div/section/div/div/table/tbody/tr[{i}]"
                )
                id_nodes = tree.xpath(f"{row}/td[1]/a/text()")
                sum_nodes = tree.xpath(f"{row}/td[2]/text()")
                if not id_nodes or not sum_nodes:
                    continue
                cve_id, cve_sum = id_nodes[0], sum_nodes[0]

                # Tenable kadang balikin hasil yang gak beneran nyebut tech-nya --
                # validasi tech-nya ada literal di summary sebelum dipakai.
                if not re.search(rf"\b{re.escape(tech_enc.replace('+', ' '))}\b", cve_sum.lower()):
                    continue
                if cve_id in seen:
                    continue
                seen.add(cve_id)
                out.append(
                    {
                        "tech": tech_enc,
                        "id": cve_id,
                        "link": f"https://www.tenable.com/cve/{cve_id}",
                        "summary": cve_sum,
                    }
                )
        return out

    def _mitre_detail(self, ctx: ScrapeContext, cand: dict[str, str]) -> dict[str, Any] | None:
        try:
            data = ctx.http.get(f"{_MITRE_URL}/{cand['id']}").json()
        except Exception as e:  # MITRE kadang balikin bentuk gak terduga
            raise ParseError(f"MITRE detail gak kebaca buat {cand['id']}: {e}") from e

        cna = data.get("containers", {}).get("cna", {})

        references = [r["url"] for r in cna.get("references", []) if "url" in r]

        affected: list[str] = []
        seen_products: set[str] = set()
        for aff in cna.get("affected", []):
            product = aff.get("product")
            if not product or product in seen_products:
                continue
            seen_products.add(product)
            for version in aff.get("versions", []):
                if version.get("status") != "affected":
                    continue
                if "lessThan" in version:
                    constraint = f"< {version['lessThan']}"
                elif "lessThanOrEqual" in version:
                    constraint = f"<= {version['lessThanOrEqual']}"
                elif "version" in version:
                    constraint = f"<= {version['version']}"
                else:
                    continue
                affected.append(f"{product}: {constraint}")

        base_score = 0.0
        severity = None
        vector = ""
        for metric_group in cna.get("metrics", []):
            for key, metric in metric_group.items():
                if key in ("scenarios", "format"):
                    continue
                score = metric.get("baseScore", 0)
                if base_score <= score:
                    base_score = score
                    vector = metric.get("vectorString", "")
                    severity = metric.get("baseSeverity")

        solutions = "".join(
            s["value"] for s in cna.get("solutions", []) if s.get("lang") == "en"
        ) or "No solution yet"

        cve_meta = data.get("cveMetadata", {})

        return {
            "cve_id": cand["id"],
            "tech": cand["tech"],
            "link": cand["link"],
            "summary": cand["summary"],
            "published": _mitre_date(cve_meta.get("datePublished")),
            "cve_modified_date": _mitre_date(cve_meta.get("dateUpdated"))
            or _mitre_date(cve_meta.get("datePublished")),
            "references": references,
            "affected": affected,
            "solutions": solutions,
            "cve_score": base_score,
            "cve_severity": severity,
            "cvss_vector": vector,
        }
