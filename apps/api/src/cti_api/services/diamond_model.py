"""Port `diamond_model_service.py`. Fase 7.4 Grup A (2026-09-23) --
internal helper `campaign.py` doang, gak ada endpoint sendiri.

TA profile lookup pakai `AsyncTAProfileRepo.list_profiles_by_names()`
(exact match) -- ganti `$regex ^{name}$` per-TA legacy (yang efeknya
SAMA persis, exact match case-insensitive, cuma method-nya beda)."""

from __future__ import annotations

from typing import Any

from cti_core.db.repositories.ta import AsyncTAProfileRepo
from sqlalchemy.ext.asyncio import AsyncSession

_TACTIC_KEYWORDS: dict[str, list[str]] = {
    "initial_access": [
        "phishing", "spearphishing", "exploit public", "supply chain", "drive-by",
        "trusted relationship", "valid accounts", "external remote", "hardware",
        "initial", "t1566", "t1190", "t1195", "t1133", "t1091", "t1200",
    ],
    "execution": [
        "script", "powershell", "command", "execution", "rundll", "regsvr",
        "mshta", "wscript", "cscript", "macro", "t1059", "t1203", "t1204",
    ],
    "persistence": [
        "scheduled task", "cron", "registry run", "startup", "boot", "persistence",
        "bootkit", "web shell", "account creation", "t1053", "t1547", "t1543",
        "t1505", "t1136",
    ],
    "privilege_escalation": [
        "privilege", "escalation", "bypass uac", "sudo", "setuid", "access token",
        "t1548", "t1134", "t1055",
    ],
    "defense_evasion": [
        "obfuscat", "masquerad", "evasion", "disable security", "rootkit",
        "timestomp", "indicator removal", "t1027", "t1036", "t1070", "t1562",
    ],
    "credential_access": [
        "credential", "brute force", "password", "kerberos", "mimikatz", "lsass",
        "ntlm", "t1003", "t1110", "t1555", "t1212",
    ],
    "discovery": [
        "discovery", "enumeration", "network scan", "port scan", "system info",
        "account discovery", "t1016", "t1018", "t1049", "t1057", "t1082",
    ],
    "lateral_movement": [
        "lateral", "pass the hash", "pass the ticket", "remote service", "rdp",
        "smb", "psexec", "wmi", "t1021", "t1550", "t1534",
    ],
    "collection": [
        "collection", "data staged", "screen capture", "keylog", "clipboard",
        "email collect", "t1005", "t1025", "t1056", "t1113", "t1114",
    ],
    "exfiltration": [
        "exfiltrat", "data transfer", "t1020", "t1030", "t1041", "t1048",
    ],
    "command_and_control": [
        "c2", "command and control", "beacon", "dns tunnel", "http tunnel",
        "cobaltstrike", "cobalt strike", "t1071", "t1090", "t1095", "t1102",
        "t1572",
    ],
    "impact": [
        "ransomware", "wiper", "denial of service", "dos", "destructive",
        "defacement", "encrypt", "t1486", "t1485", "t1489", "t1498",
    ],
}  # fmt: skip

_SOPHISTICATION_ORDER = ["low", "medium", "high", "nation-state"]


def _detect_tactic(technique: str) -> str:
    tl = technique.lower()
    for tactic, keywords in _TACTIC_KEYWORDS.items():
        for kw in keywords:
            if kw in tl:
                return tactic
    return "other"


def _group_techniques_by_tactic(techniques: list[str]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for tech in techniques:
        tactic = _detect_tactic(tech)
        grouped.setdefault(tactic, []).append(tech)
    return grouped


def _highest_sophistication(levels: list[str | None]) -> str | None:
    best_idx = -1
    best = None
    for lvl in levels:
        if lvl and lvl.lower() in _SOPHISTICATION_ORDER:
            idx = _SOPHISTICATION_ORDER.index(lvl.lower())
            if idx > best_idx:
                best_idx = idx
                best = lvl.lower()
    return best


def _compute_confidence(dm: dict[str, Any]) -> str:
    adv = dm["adversary"]
    inf = dm["infrastructure"]
    cap = dm["capability"]
    vic = dm["victim"]

    filled = 0
    total = 8

    if adv.get("threat_actors"):
        filled += 1
    if adv.get("sponsoring_nations"):
        filled += 1
    if inf.get("domains") or inf.get("ips") or inf.get("urls"):
        filled += 2
    if cap.get("attack_techniques"):
        filled += 1
    if cap.get("cve_exploited"):
        filled += 1
    if vic.get("industries"):
        filled += 1
    if vic.get("countries"):
        filled += 1

    ratio = filled / total
    if ratio >= 0.75:
        return "high"
    if ratio >= 0.4:
        return "medium"
    return "low"


def _detect_direction(grouped_techniques: dict[str, list[str]]) -> str:
    has_initial = bool(grouped_techniques.get("initial_access"))
    has_lateral = bool(grouped_techniques.get("lateral_movement"))
    has_exfil = bool(
        grouped_techniques.get("exfiltration") or grouped_techniques.get("command_and_control")
    )

    if has_lateral:
        return "lateral"
    if has_exfil and not has_initial:
        return "outbound"
    return "inbound"


def _build_diamond_model(
    campaign: dict[str, Any], ta_profiles: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    iocs: list[dict[str, Any]] = campaign.get("iocs", [])
    domains = [i["value"] for i in iocs if i.get("type") == "domain"]
    ips = [i["value"] for i in iocs if i.get("type") == "ip"]
    urls = [i["value"] for i in iocs if i.get("type") == "url"]

    dominant_tas: list[str] = campaign.get("dominant_tas", [])
    profiles = [ta_profiles[ta] for ta in dominant_tas if ta in ta_profiles]

    actor_types = list(
        {
            p.get("identity", {}).get("actor_type")
            for p in profiles
            if p.get("identity", {}).get("actor_type")
        }
    )
    sponsoring_nations = list(
        {
            p.get("identity", {}).get("sponsoring_nation")
            for p in profiles
            if p.get("identity", {}).get("sponsoring_nation")
        }
    )
    sophistication_levels = [
        p.get("capability_assessment", {}).get("sophistication_level") for p in profiles
    ]
    sophistication = _highest_sophistication(sophistication_levels)

    techniques: list[str] = campaign.get("attack_techniques", [])
    grouped_techniques = _group_techniques_by_tactic(techniques)

    malware: list[str] = []
    tools: list[str] = []
    for p in profiles:
        cap = p.get("capability_assessment", {})
        for m in cap.get("known_malware", []):
            name = m.get("name") if isinstance(m, dict) else m
            if name and name not in malware:
                malware.append(name)
        for t in cap.get("known_tools", []):
            if t and t not in tools:
                tools.append(t)

    org_types: list[str] = []
    for p in profiles:
        tp = p.get("targeting_profile", {})
        for ot in tp.get("targeted_organization_types", []):
            if ot and ot not in org_types:
                org_types.append(ot)

    adversary = {
        "threat_actors": dominant_tas,
        "actor_types": actor_types,
        "sponsoring_nations": sponsoring_nations,
        "sophistication": sophistication,
    }
    infrastructure = {
        "domains": domains,
        "ips": ips,
        "urls": urls,
        "c2_indicators": urls[:5],
    }
    capability = {
        "attack_techniques": grouped_techniques,
        "malware": malware,
        "tools": tools,
        "cve_exploited": campaign.get("cve_ids", []),
    }
    victim = {
        "industries": campaign.get("dominant_industries", []),
        "countries": campaign.get("dominant_countries", []),
        "organization_types": org_types,
    }

    dm = {
        "adversary": adversary,
        "infrastructure": infrastructure,
        "capability": capability,
        "victim": victim,
    }

    dm["meta"] = {
        "timestamps": {
            "first_seen": campaign.get("first_seen", ""),
            "last_seen": campaign.get("last_seen", ""),
        },
        "confidence": _compute_confidence(dm),
        "direction": _detect_direction(grouped_techniques),
    }

    return dm


async def build_diamond_models(session: AsyncSession, campaigns: list[dict[str, Any]]) -> None:
    """Attach `diamond_model` ke tiap campaign IN-PLACE. Batch-fetch TA
    profiles sekali buat semua campaign."""
    all_tas: set[str] = set()
    for c in campaigns:
        for ta in c.get("dominant_tas", []):
            if ta:
                all_tas.add(ta)

    ta_profiles: dict[str, dict[str, Any]] = {}
    if all_tas:
        rows = await AsyncTAProfileRepo(session).list_profiles_by_names(list(all_tas))
        by_lower = {row.actor_name.lower(): row.profile for row in rows}
        for ta in all_tas:
            key = ta.lower()
            if key in by_lower:
                ta_profiles[ta] = by_lower[key]

    for c in campaigns:
        c["diamond_model"] = _build_diamond_model(c, ta_profiles)
