"""Rute alert TWEET -> topik Telegram (Fase 10.E). PURE FUNCTION, port
`_sendAlert()` di `TwitterScrap/twitter.py` / `twitter30.py`.

Kenapa bukan `routing.route()` (artikel): cascade-nya mirip tapi TIDAK sama --
tweet punya aturan sendiri (`new claim on the shame-site` dibuang, `#threatreport`
= laporan vendor, `new hacktivist alliance`, `ransomware alert` dibuang) dan
cek "industri OT" di sini mencari kata kunci di TEKS pesan, bukan di
`industries_impacted` hasil LLM. Menyatukannya berarti mengubah perilaku salah
satunya. Urutan `elif` WAJIB persis ini.

Hasil: daftar topik (0, 1, atau 2). Dua topik = cabang terakhir yang mengirim ke `ot` DAN
ke topik generik (perilaku asli: `send_alert_ot` lalu `send_alert` tetap jalan).

DEVIASI dari legacy (2026-10-02, permintaan user): tweet "umum" -- yang tidak masuk kategori khusus
(zero_day, data_breach, vendor_report, ot, tech_stack, tech_stack_unrelated) -- dulu dibagi ke
`global`/`apac`/`apac_indo`/`apt`, thread yang DIBAGI dengan alert artikel. Sekarang semuanya ke
`feed_twitter` (`FEED_TOPIC`), thread khusus Twitter. Kategori khusus TIDAK berubah. Membalik ke
legacy: git history (`_generic_topic` + field `news_type`/`mentioned_group`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_VULN_KEYWORDS = [
    "flaws? (.+)?(enables?|expose|lets?|allows?)",
    "critical (.+)?(flaws?|vulnerability|vulnerabilities)",
    "(vulnerability|vulnerabilities) (.+)?(allows?|exposes?|enables?|lets?)",
]
_OT_KEYWORDS = [
    "critical infrastructure",
    "energy & utilities",
    "manufacturing & industrial",
    "transportation & logistics",
    "aerospace & defense contractors",
]
_RE_INDONESIA = re.compile(r"\bindonesia[n]?\b")
_FLAG_INDONESIA = "🇮🇩"

FEED_TOPIC = "feed_twitter"
"""Kunci `TELEGRAM__THREAD_IDS` untuk tweet umum (lihat DEVIASI di docstring modul)."""


@dataclass(frozen=True)
class TweetRoutingInput:
    msg_data: str
    cve_list: list[str]
    related_tech_status: bool
    report_status: bool
    ot_status: bool
    databreach_list: list[str]
    zero_day_list: list[str]


def _is_indonesia(text: str) -> bool:
    low = text.lower()
    return bool(_RE_INDONESIA.search(low)) or _FLAG_INDONESIA in low


def route_tweet(inp: TweetRoutingInput) -> list[str]:
    low = inp.msg_data.lower()
    generic = FEED_TOPIC

    if inp.zero_day_list:
        return ["zero_day"]
    if inp.databreach_list:
        return ["data_breach_indo" if _is_indonesia(inp.msg_data) else "data_breach"]
    if "new claim on the shame-site" in low:
        return []
    if inp.report_status:
        return ["vendor_report"]
    if inp.ot_status:
        return ["ot"]
    if inp.related_tech_status:
        return ["tech_stack"]
    if inp.cve_list:  # (related_tech_status di sini pasti False)
        return ["tech_stack_unrelated"]
    if "#threatreport" in low:
        return ["vendor_report"]
    if "ransomware alert" in low:
        return []
    if "new hacktivist alliance" in low:
        return [generic]

    if any(re.search(rf"\b{kw.lower()}\b", low) for kw in _VULN_KEYWORDS):
        return ["tech_stack_unrelated"]
    topics = ["ot"] if any(kw in low for kw in _OT_KEYWORDS) else []
    return [*topics, generic]
