"""Port `ScraperNewsWeb/app/services/source_score_service.py`. Fase 7.3
(router `intelligence`, Bagian 5). Heuristik statis (grading Admiralty
per NAMA sumber) -- beda dari `cti_core.db.repositories.source_reliability`
(Bagian 2, grading MANUAL analis tersimpan di DB): yang ini murni fungsi
Python, gak nyentuh DB sama sekali, lookup tabel hardcoded + fuzzy
substring match. Dua-duanya sengaja hidup berdampingan, sama kayak
`mitreValidator.py` vs `attack_sync_service.py` (plan §6: mirip tapi
beda concern, bukan duplikat buat digabung)."""

from __future__ import annotations

from typing import Any

# Admiralty source reliability grades:
#   A - Completely reliable   B - Usually reliable   C - Fairly reliable
#   D - Not usually reliable  E - Unreliable         F - Cannot be judged
_SOURCE_RELIABILITY: dict[str, str] = {
    # Government / official bodies
    "CISA": "A",
    "NIST": "A",
    "NSA": "A",
    "FBI": "A",
    "NCSC": "A",
    "Europol": "A",
    "ENISA": "A",
    "CERT": "A",
    # Top-tier vendor threat intelligence
    "Mandiant": "A",
    "Google": "A",
    "CrowdStrike": "A",
    "Recorded Future": "A",
    "Microsoft": "A",
    "Cisco Talos": "A",
    "Talos Intelligence": "A",
    "Unit 42": "A",
    "Palo Alto": "A",
    "Secureworks": "A",
    "IBM X-Force": "A",
    "Trend Micro": "A",
    "SentinelOne": "A",
    "Sophos": "A",
    # Strong secondary vendor
    "Kaspersky": "A",
    "Securelist": "A",
    "ESET": "A",
    "Symantec": "A",
    "Broadcom": "A",
    "Check Point": "A",
    "WithSecure": "A",
    "Huntress": "A",
    # Reputable independent security media
    "Krebs on Security": "A",
    "BleepingComputer": "B",
    "The Hacker News": "B",
    "Dark Reading": "B",
    "SecurityWeek": "B",
    "Threatpost": "B",
    "InfoSecurity Magazine": "B",
    "SC Media": "B",
    "CSO Online": "B",
    "Help Net Security": "B",
    "Naked Security": "B",
    "Malwarebytes": "B",
    # General technology press
    "Wired": "C",
    "Ars Technica": "C",
    "ZDNet": "C",
    "TechCrunch": "C",
    "The Register": "C",
    "Reuters": "C",
    "BBC": "C",
    "Associated Press": "C",
    "Bloomberg": "C",
    "Wall Street Journal": "C",
    "Washington Post": "C",
    # Less security-focused / tabloid-adjacent
    "Vice": "D",
    "Motherboard": "D",
    "Daily Mail": "D",
    "NY Post": "D",
}

_RELIABILITY_LABELS: dict[str, str] = {
    "A": "Completely reliable",
    "B": "Usually reliable",
    "C": "Fairly reliable",
    "D": "Not usually reliable",
    "E": "Unreliable",
    "F": "Cannot be judged",
}

_RELIABILITY_ORDER = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4, "F": 5}


def get_source_reliability(source: str) -> str:
    if source in _SOURCE_RELIABILITY:
        return _SOURCE_RELIABILITY[source]
    src_lower = source.lower()
    for key, grade in _SOURCE_RELIABILITY.items():
        if key.lower() in src_lower or src_lower in key.lower():
            return grade
    return "F"


def score_sources(sources: list[str]) -> list[dict[str, Any]]:
    result = []
    for source in sources:
        rel = get_source_reliability(source)
        result.append(
            {
                "source": source,
                "reliability_grade": rel,
                "reliability_label": _RELIABILITY_LABELS[rel],
                "known": rel != "F",
            }
        )
    result.sort(key=lambda x: (_RELIABILITY_ORDER.get(str(x["reliability_grade"]), 5), x["source"]))
    return result
