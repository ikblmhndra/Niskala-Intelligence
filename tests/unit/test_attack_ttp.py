"""`cti_core.attack_ttp` -- normalisasi TTP LLM ke katalog ATT&CK.

Kasus diambil persis dari QA 2026-10-01: BUG-C01 (MITRE Heatmap kolom dobel),
BUG-04 (Dashboard/Exec), BUG-B8 (modal artikel Newsroom), BUG-C18 (deskripsi
ATT&CK mentah)."""

from __future__ import annotations

import pytest
from cti_core.attack_ttp import (
    NormalizedTTP,
    TechniqueCatalog,
    clean_attack_text,
    name_key,
    normalize_ttps,
)
from cti_enrich.stages.extract_ttps import Technique, TtpResult, normalize_ttp_result

ENT = ("enterprise-attack",)

CATALOG = TechniqueCatalog.build(
    techniques=[
        ("T1003", "OS Credential Dumping", ENT),
        ("T1068", "Exploitation for Privilege Escalation", ENT),
        ("T1110", "Brute Force", ENT),
        ("T1548", "Abuse Elevation Control Mechanism", ENT),
        ("T1570", "Lateral Tool Transfer", ENT),
        ("T1203", "Exploitation for Client Execution", ENT),
        ("T1547", "Boot or Logon Autostart Execution", ENT),
        ("T1518.001", "Security Software Discovery", ENT),
        ("T1566", "Phishing", ENT),
        ("T1566.001", "Spearphishing Attachment", ENT),
        ("T1566.002", "Spearphishing Link", ENT),
        ("T1598", "Phishing for Information", ENT),
        ("T1598.002", "Spearphishing Attachment", ENT),
        ("T1598.003", "Spearphishing Link", ENT),
        ("T1059", "Command and Scripting Interpreter", ENT),
        ("T1059.001", "PowerShell", ENT),
        ("T0865", "Spearphishing Attachment", ("ics-attack",)),
    ],
    tactics=["Privilege Escalation", "Persistence", "Lateral Movement", "Initial Access"],
    revoked=[
        ("T1086", "PowerShell", "T1059.001"),
        ("T1193", "Spearphishing Attachment", "T1566.001"),
    ],
)


def _one(raw_id: str, raw_name: str) -> tuple[str, str] | None:
    out = normalize_ttps([(raw_id, raw_name)], CATALOG)
    return (out[0].ttp_id, out[0].ttp_name) if out else None


@pytest.mark.parametrize(
    ("raw_id", "raw_name", "expected"),
    [
        # BUG-C01 / BUG-04: nama benar, ID salah -> nama yang menang
        (
            "T1548",
            "Exploitation for Privilege Escalation",
            ("T1068", "Exploitation for Privilege Escalation"),
        ),
        ("T1110", "Credential Dumping", ("T1003", "OS Credential Dumping")),
        (
            "T1548",
            "Abuse Elevation Control Mechanism",
            ("T1548", "Abuse Elevation Control Mechanism"),
        ),
        ("T1570", "Lateral Tool Transfer", ("T1570", "Lateral Tool Transfer")),
        # BUG-B8: nama karangan, ID valid -> nama kanonik
        ("T1203", "Remote Code Execution", ("T1203", "Exploitation for Client Execution")),
        ("T1566.001", "Social Engineering", ("T1566.001", "Spearphishing Attachment")),
        ("T1598.003", "Targeted phishing campaigns", ("T1598.003", "Spearphishing Link")),
        # nama ambigu -> ID LLM / keluarga ID LLM jadi penentu
        ("T1598.002", "Spearphishing Attachment", ("T1598.002", "Spearphishing Attachment")),
        ("T1566", "Spearphishing Attachment", ("T1566.001", "Spearphishing Attachment")),
        ("T9999", "Spearphishing Attachment", ("T1566.001", "Spearphishing Attachment")),
        # sub-technique dari technique yang disebut namanya -> lebih spesifik dipertahankan
        ("T1059.001", "Command and Scripting Interpreter", ("T1059.001", "PowerShell")),
        # technique revoked (STIX) -> pengganti, by nama atau by ID
        ("T1086", "PowerShell scripts", ("T1059.001", "PowerShell")),
        ("t1193 ", "spearphishing attachment", ("T1566.001", "Spearphishing Attachment")),
        # format tampilan ATT&CK / ID ikut di nama
        ("", "Phishing: Spearphishing Link", ("T1566.002", "Spearphishing Link")),
        ("T1110", "Brute Force (T1110)", ("T1110", "Brute Force")),
    ],
)
def test_resolves_llm_pairs_to_catalog(
    raw_id: str, raw_name: str, expected: tuple[str, str]
) -> None:
    assert _one(raw_id, raw_name) == expected


@pytest.mark.parametrize(
    ("raw_id", "raw_name"),
    [
        # BUG-C01: nama TACTIC bukan technique
        ("T1548", "Privilege Escalation"),
        ("T1570", "Lateral Movement"),
        ("T1547", "Persistence"),
        ("TA0004", "Privilege Escalation"),
        # ID & nama sama-sama gak dikenal
        ("T9999", "Totally Made Up"),
        ("not-an-id", ""),
    ],
)
def test_drops_tactics_and_unknowns(raw_id: str, raw_name: str) -> None:
    assert _one(raw_id, raw_name) is None


def test_heatmap_case_collapses_to_one_row_per_id_and_keeps_raw_text() -> None:
    """Satu artikel dengan pasangan-pasangan yang di QA bikin kolom dobel."""
    out = normalize_ttps(
        [
            ("T1548", "Exploitation for Privilege Escalation"),
            ("T1548", "Abuse Elevation Control Mechanism"),
            ("T1548", "Privilege Escalation"),
            ("T1068", "Exploitation for Privilege Escalation"),
        ],
        CATALOG,
    )
    assert out == [
        NormalizedTTP(
            "T1068",
            "Exploitation for Privilege Escalation",
            "T1548",
            "Exploitation for Privilege Escalation",
        ),
        NormalizedTTP(
            "T1548",
            "Abuse Elevation Control Mechanism",
            "T1548",
            "Abuse Elevation Control Mechanism",
        ),
    ]


def test_tactic_name_that_is_also_a_technique_name_is_kept() -> None:
    catalog = TechniqueCatalog.build(
        techniques=[("T1999", "Execution", ENT)], tactics=["Execution"]
    )
    assert [n.ttp_id for n in normalize_ttps([("T1999", "Execution")], catalog)] == ["T1999"]


def test_renamed_alias_only_applies_when_target_is_in_catalog() -> None:
    catalog = TechniqueCatalog.build(techniques=[("T1110", "Brute Force", ENT)])
    # T1003 gak ada di katalog -> alias "Credential Dumping" gak aktif, ID LLM dipakai
    assert normalize_ttps([("T1110", "Credential Dumping")], catalog)[0].ttp_id == "T1110"


def test_empty_catalog_is_passthrough_with_format_and_tactic_guard() -> None:
    empty = TechniqueCatalog()
    out = normalize_ttps(
        [("t1059", "Command Scripting"), ("T1548", "Privilege Escalation"), ("bogus", "x")], empty
    )
    assert out == [NormalizedTTP("T1059", "Command Scripting", "t1059", "Command Scripting")]


def test_name_key_is_cosmetic_only() -> None:
    assert name_key("  OS  Credential" + chr(0x2013) + "Dumping. ") == "os credential-dumping"
    assert name_key("Phishing [T1566]") == "phishing"


def test_normalize_ttp_result_rewrites_techniques_for_alert_and_persist() -> None:
    result = TtpResult(
        has_techniques=True,
        techniques=[
            Technique("T1110", "Credential Dumping", evidence="dumped LSASS"),
            Technique("T1547", "Persistence"),
        ],
    )
    out = normalize_ttp_result(result, CATALOG)
    assert out.has_techniques
    assert [(t.technique_id, t.technique_name, t.evidence) for t in out.techniques] == [
        ("T1003", "OS Credential Dumping", "dumped LSASS")
    ]
    assert out.techniques[0].extracted_id == "T1110"
    assert out.techniques[0].extracted_name == "Credential Dumping"

    only_tactics = TtpResult(has_techniques=True, techniques=[Technique("T1547", "Persistence")])
    assert normalize_ttp_result(only_tactics, CATALOG) == TtpResult(has_techniques=False)


def test_clean_attack_text_strips_citations_and_markdown_links() -> None:
    """BUG-C18 -- contoh dari deskripsi T1190."""
    raw = (
        "Exploited MySQL (Citation: NVD CVE-2016-6662) and "
        "[Exploitation for Stealth](https://attack.mitre.org/techniques/T1211) "
        "via <code>mysqld</code>.(Citation: A)(Citation: B)\n\nSecond paragraph."
    )
    assert clean_attack_text(raw) == (
        "Exploited MySQL and Exploitation for Stealth via mysqld.\n\nSecond paragraph."
    )
    assert clean_attack_text(None) == ""
