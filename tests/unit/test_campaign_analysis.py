"""Unit test fungsi murni `cti_api.services.campaign_analysis` (kill
chain + campaign links + faktor pure severity, gak butuh DB). Fase 7.4
Grup A."""

from __future__ import annotations

from cti_api.services import campaign_analysis as ca


def test_analyze_kill_chain_no_techniques() -> None:
    result = ca.analyze_kill_chain([])
    assert result["phases_covered"] == []
    assert result["completeness_score"] == 0
    assert result["completeness_label"] == "limited"
    assert result["operational_risk"] == "low"


def test_analyze_kill_chain_full_chain_critical() -> None:
    techniques = [
        "T1566", "T1059", "T1547", "T1548", "T1027", "T1003",
        "T1083", "T1021", "T1005", "T1041", "T1071", "T1486",
    ]  # fmt: skip
    result = ca.analyze_kill_chain(techniques)
    assert len(result["phases_covered"]) == 12
    assert result["completeness_score"] == 100
    assert result["completeness_label"] == "full_chain"
    assert result["operational_risk"] == "critical"  # has initial+exec+exfil


def test_analyze_kill_chain_extracts_subtechnique_ids() -> None:
    result = ca.analyze_kill_chain(["T1566.001 Spearphishing Attachment"])
    assert "initial_access" in result["phases_covered"]


def test_analyze_kill_chain_unknown_technique_ignored() -> None:
    result = ca.analyze_kill_chain(["T9999", "not a technique"])
    assert result["phases_covered"] == []


def test_compute_campaign_links_no_overlap_no_link() -> None:
    campaigns = [
        {"cluster_id": "a", "cluster_name": "A", "dominant_tas": ["Apt41"]},
        {"cluster_id": "b", "cluster_name": "B", "dominant_tas": ["Lazarus"]},
    ]
    links = ca.compute_campaign_links(campaigns)
    assert links == []


def test_compute_campaign_links_same_actor_scores_high() -> None:
    campaigns = [
        {"cluster_id": "a", "cluster_name": "A", "dominant_tas": ["Apt41", "Turla"]},
        {"cluster_id": "b", "cluster_name": "B", "dominant_tas": ["Apt41", "Turla"]},
    ]
    links = ca.compute_campaign_links(campaigns)
    assert len(links) == 1
    assert links[0]["link_type"] == "same_actor"
    assert links[0]["source_id"] == "a"
    assert links[0]["target_id"] == "b"
    assert links[0]["shared_tas"] == ["Apt41", "Turla"]


def test_compute_campaign_links_shared_infra_type() -> None:
    campaigns = [
        {
            "cluster_id": "a",
            "cluster_name": "A",
            "iocs": [{"type": "domain", "value": "evil.example"}],
        },
        {
            "cluster_id": "b",
            "cluster_name": "B",
            "iocs": [{"type": "domain", "value": "evil.example"}],
        },
    ]
    links = ca.compute_campaign_links(campaigns)
    assert len(links) == 1
    assert links[0]["link_type"] == "shared_infra"


def test_compute_campaign_links_weak_overlap_below_threshold_excluded() -> None:
    campaigns = [
        {"cluster_id": "a", "cluster_name": "A", "cve_ids": ["CVE-2024-0001"]},
        {"cluster_id": "b", "cluster_name": "B", "cve_ids": ["CVE-2024-0002"]},
    ]
    links = ca.compute_campaign_links(campaigns)
    assert links == []


def test_velocity_factor_thresholds() -> None:
    assert ca._velocity_factor(6.0) == 100.0
    assert ca._velocity_factor(4.0) == 80.0
    assert ca._velocity_factor(2.0) == 60.0
    assert ca._velocity_factor(0.5) == 40.0
    assert ca._velocity_factor(0.1) == 20.0


def test_source_quality_factor_averages_known_grades() -> None:
    articles = [{"source_reliability": "A"}, {"source_reliability": "C"}]
    # A=100, C=60 -> avg 80
    assert ca._source_quality_factor(articles) == 80.0


def test_source_quality_factor_no_known_grades_defaults_50() -> None:
    articles = [{"source_reliability": ""}, {"source_reliability": "Z"}]
    assert ca._source_quality_factor(articles) == 50.0
