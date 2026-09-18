"""Stage: cari mention CVE ID di teks -- port `re.findall(r"cve-\\d{4}-\\d{4,}",
...)` dari `nlp.py:411` (title) dan `:460` (body). Regex TETAP `\\d{4,}` (4+
digit, bukan `\\d{4,7}` kayak `iocExtractor._RE_CVE`) -- beda dengan
sengaja, ini bukan salah ketik yang perlu diseragamkan: dua konteks beda
(mention-tracking longgar di sini vs IOC ekstraksi ketat di sana).

Hasil TETAP lowercase (gak di-`.upper()` di sini) -- kode lama nyimpen
`cve_list_title`/`cve_list_body` apa adanya lowercase buat
`update_cve_mention`, uppercase cuma di titik panggil `checkCVE()`
(`stages/score.py`)."""

from __future__ import annotations

import re

_RE_CVE_MENTION = re.compile(r"cve-\d{4}-\d{4,}")


def extract_cves(text: str) -> list[str]:
    if not text:
        return []
    return re.findall(_RE_CVE_MENTION, text.lower())
