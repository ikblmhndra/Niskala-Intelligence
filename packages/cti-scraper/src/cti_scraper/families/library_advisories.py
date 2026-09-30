"""LibraryAdvisoryScraper -- advisory keamanan baru untuk library yang dipantau
(Fase 10.E). Gantiin `techstackLibrary/techstack{NPM,PYPI,GO}.py`: tiga skrip
yang isinya sama persis kecuali ekosistem dan daftar paketnya.

Alur (sama dengan skrip lama): `deps.dev` -> versi terbaru paket -> tiap versi
punya `advisoryKeys` -> detail advisory dari `osv.dev` -> satu notice Telegram.

Bug skrip lama yang TIDAK ikut ter-port:
  - Pesan dibangun SETELAH loop advisory (indentasi) -> versi dengan 3 advisory
    cuma mengabarkan yang TERAKHIR, dua lainnya gak pernah muncul. Sekarang tiap
    advisory jadi satu notice.
  - "5 versi terbaru" dipilih dari versi yang sudah dinormalisasi (`re.sub`
    non-angka) lalu dicocokkan ke versi MENTAH -> versi ber-prefix `v` (Go)
    atau ber-sufiks gak pernah cocok.
  - "Fixed version terbaru" dibandingkan sebagai STRING (`"1.9" > "1.10"`).
  - Bot token + chat + thread Telegram HARDCODED di ketiga skrip (masuk daftar
    rotasi Fase 10.F); sekarang lewat topik `library_advisory`.
  - `Details` advisory bisa berkilo-kilo karakter dan gak di-escape -> pesan
    melewati batas 4096 Telegram / HTML rusak, errornya ditelan. Sekarang
    di-escape dan dipotong.

Dedup key = `<advisory_id>:<tanggal modified>` -- identitas yang sama dengan
`offset/techstack_*_offset.txt` lama, jadi file offset produksi bisa dipakai
buat warm start (`tools/seed/fase10_warm_start.py`). Advisory yang sama muncul
di banyak versi/paket; satu run cuma nge-fetch dan mengabarkannya sekali.
"""

from __future__ import annotations

import html
import re
from collections.abc import Iterator
from typing import Any, ClassVar
from urllib.parse import quote

from cti_scraper.base import BaseScraper, ScrapeContext
from cti_scraper.errors import ParseError
from cti_scraper.items import NoticeItem

_DEPS_DEV = "https://api.deps.dev/v3/systems"
_OSV = "https://api.osv.dev/v1/vulns"
_LATEST_VERSIONS = 5
_MAX_DETAILS_CHARS = 1200


def version_key(version: str) -> tuple[int, ...]:
    """Kunci urut numerik: "v1.10.2" > "v1.9.0". Bagian non-angka diabaikan
    (`1.0.0-beta` = `1.0.0`, sama dengan normalisasi skrip lama)."""
    return tuple(int(n) for n in re.findall(r"\d+", version))


def _date(iso: str) -> str:
    return iso[:10] if re.match(r"\d{4}-\d{2}-\d{2}", iso or "") else ""


def _fixed_versions(advisory: dict[str, Any]) -> list[str]:
    fixed: list[str] = []
    for affected in advisory.get("affected", []):
        for rng in affected.get("ranges", []):
            fixed += [e["fixed"] for e in rng.get("events", []) if "fixed" in e]
    return fixed


class LibraryAdvisoryScraper(BaseScraper):
    __abstract__ = True

    ecosystem: ClassVar[str]
    """Nama sistem deps.dev: "npm" | "pypi" | "go"."""
    label: ClassVar[str]
    """Teks judul pesan ("NPM", "PYPI", "GOLANG") -- persis skrip lama."""
    packages: ClassVar[tuple[str, ...]]
    """Nama paket APA ADANYA (Go: `github.com/docker/docker`); di-quote di sini."""
    topic: ClassVar[str] = "library_advisory"

    def fetch(self, ctx: ScrapeContext) -> Iterator[NoticeItem]:
        advisories: dict[str, dict[str, Any] | None] = {}  # cache per run
        yielded: set[str] = set()
        found = 0

        for package in self.packages:
            base = f"{_DEPS_DEV}/{self.ecosystem}/packages/{quote(package, safe='')}"
            listing = self._get_json(ctx, base)
            versions = [v["versionKey"]["version"] for v in listing.get("versions", [])]
            latest = sorted(set(versions), key=version_key, reverse=True)[:_LATEST_VERSIONS]

            for version in latest:
                info = self._get_json(ctx, f"{base}/versions/{quote(version, safe='')}")
                for key in info.get("advisoryKeys", []):
                    advisory_id = key["id"]
                    if advisory_id not in advisories:
                        advisories[advisory_id] = self._get_json(
                            ctx, f"{_OSV}/{quote(advisory_id, safe='')}", missing_ok=True
                        )
                    advisory = advisories[advisory_id]
                    if advisory is None:
                        continue
                    notice = self._notice(package, advisory)
                    if notice.key in yielded:
                        continue
                    yielded.add(notice.key)
                    if found >= self.meta.max_items:
                        return
                    found += 1
                    yield notice

    @staticmethod
    def _get_json(ctx: ScrapeContext, url: str, *, missing_ok: bool = False) -> Any:
        resp = ctx.http.get(url)
        if resp.status_code == 404 and missing_ok:
            return None
        if resp.status_code != 200:
            raise ParseError(f"{url}: HTTP {resp.status_code}")
        try:
            return resp.json()
        except ValueError as e:
            raise ParseError(f"{url}: respons bukan JSON valid -- {e}") from e

    def _notice(self, package: str, advisory: dict[str, Any]) -> NoticeItem:
        advisory_id = advisory["id"]
        published = _date(advisory.get("published", ""))
        modified = _date(advisory.get("modified", ""))

        fixed = _fixed_versions(advisory)
        latest_fixed = max(fixed, key=version_key) if fixed else None
        details = str(advisory.get("details", "")).strip()
        if len(details) > _MAX_DETAILS_CHARS:
            details = details[:_MAX_DETAILS_CHARS].rstrip() + "..."
        aliases = ", ".join(advisory.get("aliases", [])) or "-"

        text = (
            f"    === <b>NEW ADVISORYS UPDATE FOR {self.label}</b> ===\n"
            f"<b>Name</b> : {html.escape(package)}\n"
            f"<b>Advisory ID</b> : {html.escape(advisory_id)}\n"
            f"<b>Details</b> : {html.escape(details)}\n"
            f"<b>Aliases</b> : {html.escape(aliases)}\n"
            f"<b>Published</b> : {published}\n"
            f"<b>Modified</b> : {modified}\n"
            f"<b>Fixed Version</b> : {html.escape(latest_fixed) if latest_fixed else 'N/A'}\n"
            f"<b>Affected Version</b> : "
            + (f"Lower than {html.escape(latest_fixed)} Version" if latest_fixed else "N/A")
        )
        return NoticeItem(
            topic=self.topic,
            text=text,
            key=f"{advisory_id}:{modified}",
            title=f"{self.label} advisory {advisory_id} ({package})",
            url=f"https://osv.dev/vulnerability/{advisory_id}",
        )
