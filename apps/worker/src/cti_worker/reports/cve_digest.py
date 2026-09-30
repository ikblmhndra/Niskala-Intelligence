"""Laporan Top CVE -- dua varian dengan mesin yang sama:

  - mingguan (`topCve.py`): 10 CVE paling banyak disebut di ARTIKEL 7 hari
    terakhir -> topik `tech_stack`;
  - 6 jam (`TwitterScrap/trendingCve.py`): 10 CVE paling banyak disebut di TWEET
    -> `tech_stack` kalau ada yang cocok tech stack organisasi, kalau tidak
    `tech_stack_unrelated` DAN `vendor_report`.

Logika ambil-data + format di sini, pengiriman dan reset counter di
`tasks/reports.py` -- reset HARUS sesudah kirim sukses (kode lama mereset di dalam
loop SEBELUM kirim, jadi Telegram gagal = mention hilang dari laporan berikutnya).
"""

from __future__ import annotations

import datetime
import html
from dataclasses import dataclass

import httpx
from cti_core.db.models.report_state import SCOPE_NEWS, CveMention
from cti_core.db.repositories.report_state import CveMentionRepo
from sqlalchemy.orm import Session

from cti_worker.reports.cve_record import CveSummary, fetch_record, summarize

WEEKLY_WINDOW_DAYS = 7
_CANDIDATES = 50
_APPLICABLE = "[<b>Might Applicable to Organization!</b>]"


@dataclass(frozen=True)
class Digest:
    text: str
    cve_ids: list[str]
    """CVE yang dimasukkan -- counter-nya di-reset SETELAH pesan terkirim."""
    any_applicable: bool


def _summary_for(client: httpx.Client, mention: CveMention, techstack: list[str]) -> CveSummary:
    record = fetch_record(client, mention.cve_id)
    if record is None:
        return CveSummary(mention.cve_id, None, "None", "Unknown", "Unknown", False)
    return summarize(mention.cve_id, record, techstack)


def build_weekly(
    session: Session,
    client: httpx.Client,
    techstack: list[str],
    *,
    today: datetime.date,
    limit: int = 10,
) -> Digest | None:
    """Top `limit` CVE artikel. CVE yang record MITRE-nya tidak ada DILEWATI
    (sama dengan kode lama) dan tidak dihitung ke `limit`; counter-nya dibiarkan."""
    candidates = CveMentionRepo(session).top(
        SCOPE_NEWS,
        seen_since=today - datetime.timedelta(days=WEEKLY_WINDOW_DAYS),
        limit=_CANDIDATES,
    )
    lines: list[str] = []
    included: list[str] = []
    applicable = False
    for mention in candidates:
        if len(included) >= limit:
            break
        record = fetch_record(client, mention.cve_id)
        if record is None:
            continue
        s = summarize(mention.cve_id, record, techstack)
        applicable = applicable or s.applicable
        lines.append(
            f"\n    - <code>{s.cve_id}</code> ({s.score_text} <b>{s.category}</b>), "
            f"Total Mentioned: {mention.counter}\n"
            f"        Product Name: {html.escape(s.product)}\n"
            f"        Vendor Name: {html.escape(s.vendor)} {_APPLICABLE if s.applicable else ''}\n"
        )
        included.append(s.cve_id)
    if not included:
        return None
    text = (
        "\n    === <b>TOP 10 MOST MENTIONED CVE IN THE LAST 7 DAYS</b> ===\n<blockquote>"
        + "".join(lines)
        + "</blockquote>"
    )
    return Digest(text=text, cve_ids=included, any_applicable=applicable)


def build_trending(
    mentions: list[CveMention], client: httpx.Client, techstack: list[str]
) -> Digest | None:
    """Top CVE tweet. Berbeda dari mingguan: CVE tanpa record MITRE TETAP
    dilaporkan (Unknown / N/A) -- CVE yang baru ramai di tweet sering belum
    dipublikasikan."""
    if not mentions:
        return None
    lines = ["    === <b>TOP CVE MENTIONED IN THE PAST 6 HOUR(S)</b> ==="]
    applicable = False
    for mention in mentions:
        s = _summary_for(client, mention, techstack)
        applicable = applicable or s.applicable
        lines.append(
            f"\n- <code>{s.cve_id}</code> ({s.score_text} <b>{s.category}</b>), "
            f"Total Tweet: {mention.counter}\n"
            f"    Product Name: {html.escape(s.product)}\n"
            f"    Vendor Name: {html.escape(s.vendor)} {_APPLICABLE if s.applicable else ''}\n"
        )
    return Digest(
        text="".join(lines).rstrip("\n"),
        cve_ids=[m.cve_id for m in mentions],
        any_applicable=applicable,
    )
