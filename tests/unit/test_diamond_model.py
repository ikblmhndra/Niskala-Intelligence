"""Unit test fungsi murni `cti_api.services.diamond_model` (gak butuh
DB -- `build_diamond_models()` sendiri yang butuh session, dites di
integration suite). Fase 7.4 Grup A."""

from __future__ import annotations

from cti_api.services import diamond_model as dm


def test_detect_tactic_matches_keyword() -> None:
    assert dm._detect_tactic("Phishing email with malicious attachment") == "initial_access"
    assert dm._detect_tactic("Ransomware encrypts files") == "impact"


def test_detect_tactic_matches_technique_id() -> None:
    assert dm._detect_tactic("T1566") == "initial_access"
    assert dm._detect_tactic("t1486") == "impact"


def test_detect_tactic_unknown_returns_other() -> None:
    assert dm._detect_tactic("completely unrelated text xyz") == "other"


def test_group_techniques_by_tactic() -> None:
    grouped = dm._group_techniques_by_tactic(["T1566", "T1486", "T1059"])
    assert grouped["initial_access"] == ["T1566"]
    assert grouped["impact"] == ["T1486"]
    assert grouped["execution"] == ["T1059"]


def test_highest_sophistication_picks_max() -> None:
    assert dm._highest_sophistication(["low", "high", "medium"]) == "high"
    assert dm._highest_sophistication(["nation-state", "low"]) == "nation-state"


def test_highest_sophistication_ignores_unknown_and_none() -> None:
    assert dm._highest_sophistication([None, "unknown-level", "medium"]) == "medium"


def test_highest_sophistication_empty_returns_none() -> None:
    assert dm._highest_sophistication([]) is None


def test_compute_confidence_all_filled_is_high() -> None:
    campaign = {
        "adversary": {"threat_actors": ["Apt41"], "sponsoring_nations": ["China"]},
        "infrastructure": {"domains": ["evil.example"], "ips": [], "urls": []},
        "capability": {
            "attack_techniques": {"initial_access": ["T1566"]},
            "cve_exploited": ["CVE-2024-0001"],
        },
        "victim": {"industries": ["Manufacturing"], "countries": ["US"]},
    }
    assert dm._compute_confidence(campaign) == "high"


def test_compute_confidence_nothing_filled_is_low() -> None:
    campaign = {
        "adversary": {},
        "infrastructure": {},
        "capability": {},
        "victim": {},
    }
    assert dm._compute_confidence(campaign) == "low"


def test_detect_direction_lateral_movement_wins() -> None:
    grouped = {"lateral_movement": ["T1021"], "initial_access": ["T1566"]}
    assert dm._detect_direction(grouped) == "lateral"


def test_detect_direction_outbound_when_exfil_no_initial() -> None:
    grouped = {"exfiltration": ["T1041"]}
    assert dm._detect_direction(grouped) == "outbound"


def test_detect_direction_defaults_inbound() -> None:
    assert dm._detect_direction({}) == "inbound"


def test_build_diamond_model_populates_all_quadrants() -> None:
    campaign = {
        "iocs": [
            {"type": "domain", "value": "evil.example"},
            {"type": "ip", "value": "1.2.3.4"},
        ],
        "dominant_tas": ["Apt41"],
        "attack_techniques": ["T1566", "T1486"],
        "cve_ids": ["CVE-2024-0001"],
        "dominant_industries": ["Manufacturing"],
        "dominant_countries": ["US"],
        "first_seen": "2026-09-01",
        "last_seen": "2026-09-10",
    }
    ta_profiles = {
        "Apt41": {
            "identity": {"actor_type": "state-sponsored", "sponsoring_nation": "China"},
            "capability_assessment": {
                "sophistication_level": "nation-state",
                "known_malware": [{"name": "ShadowPad"}],
                "known_tools": ["Cobalt Strike"],
            },
            "targeting_profile": {"targeted_organization_types": ["government"]},
        }
    }
    result = dm._build_diamond_model(campaign, ta_profiles)
    assert result["adversary"]["sophistication"] == "nation-state"
    assert result["adversary"]["sponsoring_nations"] == ["China"]
    assert "evil.example" in result["infrastructure"]["domains"]
    assert result["capability"]["malware"] == ["ShadowPad"]
    assert result["victim"]["industries"] == ["Manufacturing"]
    assert result["meta"]["confidence"] == "high"
