"""`mitre_changelog` -- port `mitreValidator.mitreJsonURL/mitreUpdateLog` (Fase 10.E).

Fungsi murni, jadi bundle STIX kecil buatan tangan cukup. Beberapa test
mengunci bug kode lama yang sengaja diperbaiki (lihat docstring modulnya).
"""

from __future__ import annotations

import datetime

from cti_scrapers.collectors.mitre_changelog import build_changes, render

NOW = datetime.datetime(2026, 9, 26, 12, 0, 0)


def ts(days_ago: float, fraction: bool = True) -> str:
    when = NOW - datetime.timedelta(days=days_ago)
    return when.strftime("%Y-%m-%dT%H:%M:%S.%fZ" if fraction else "%Y-%m-%dT%H:%M:%SZ")


def ref(ext_id: str) -> list[dict]:
    return [
        {"source_name": "mitre-attack", "external_id": ext_id, "url": f"https://a/{ext_id}"},
        {"source_name": "other", "external_id": "zzz"},
    ]


def obj(kind: str, name: str, days_ago: float = 1, **extra: object) -> dict:
    return {
        "type": kind, "id": f"{kind}--{name}", "name": name, "created": ts(days_ago),
        "external_references": ref(name[:5]), **extra,
    }  # fmt: skip


def test_window_is_seven_days_inclusive_and_revoked_or_components_are_skipped() -> None:
    bundle = {
        "objects": [
            obj("malware", "in-window", 7),
            obj("malware", "too-old", 8),
            obj("malware", "revoked", 1, revoked=True),
            obj("x-mitre-data-component", "component", 1),
        ]
    }

    changes = build_changes(bundle, now=NOW)

    assert [r["software_name"] for r in changes["malware"]] == ["in-window"]
    assert "x-mitre-data-component" not in changes


def test_objects_missing_optional_fields_do_not_abort_the_whole_changelog() -> None:
    """Kode lama: `data['description']`/`data['x_mitre_domains']` -> KeyError, seluruh
    changelog batal gara-gara satu objek."""
    bundle = {"objects": [{"type": "malware", "id": "m1", "name": "Bare", "created": ts(1)}]}

    changes = build_changes(bundle, now=NOW)

    assert changes["malware"][0]["software_name"] == "Bare"
    assert changes["malware"][0]["software_domain"] == ""


def test_timestamps_without_fractional_seconds_are_accepted() -> None:
    bundle = {"objects": [{**obj("malware", "nofrac"), "created": ts(1, fraction=False)}]}

    assert len(build_changes(bundle, now=NOW)["malware"]) == 1


def test_subtechnique_resolves_its_parent_and_renders_the_parent_block() -> None:
    parent = obj("attack-pattern", "T1059", 400, description="parent desc")
    parent["external_references"] = ref("T1059")
    child = obj("attack-pattern", "T1059.001", 1, x_mitre_is_subtechnique=True, description="child")
    child["name"] = "PowerShell"
    child["external_references"] = ref("T1059.001")

    changes = build_changes({"objects": [parent, child]}, now=NOW)
    text, _ = render(changes)

    [row] = changes["attack-pattern"]
    assert (row["parent_technique_id"], row["parent_technique_name"]) == ("T1059", "T1059")
    assert (
        "This technique has a parent, T1059 (T1059) https://attack.mitre.org/techniques/T1059"
        in text
    )
    assert "https://attack.mitre.org/techniques/T1059/001" in text


def test_top_level_technique_has_no_empty_parent_block() -> None:
    """Kode lama mencetak 'This technique has a parent:  ()' untuk teknik non-sub."""
    tech = obj("attack-pattern", "T1234", 1, description="d")
    tech["external_references"] = ref("T1234")

    text, _ = render(build_changes({"objects": [tech]}, now=NOW))

    assert "has a parent" not in text


def test_relationship_names_are_resolved_from_the_whole_bundle() -> None:
    old_group = obj("intrusion-set", "APT-Old", 500)
    rel = {
        "type": "relationship", "id": "relationship--1", "created": ts(1),
        "source_ref": old_group["id"], "target_ref": "malware--gone",
        "relationship_type": "uses", "description": "APT-Old uses it",
    }  # fmt: skip

    [row] = build_changes({"objects": [old_group, rel]}, now=NOW)["relationship"]

    assert (row["source_ref_name"], row["target_ref_name"]) == ("APT-Old", "")  # yg gak ada: kosong


def test_render_summary_counts_and_unknown_types_get_an_empty_section() -> None:
    bundle = {
        "objects": [
            obj("malware", "m1"),
            obj("malware", "m2"),
            obj("intrusion-set", "g1", x_mitre_aliases=None, aliases=["G-One"]),
            obj("identity", "someone"),  # tipe tanpa penanganan
        ]
    }

    text, summary = render(build_changes(bundle, now=NOW))

    assert "<b>Malware</b>: 2 entries" in summary and "<b>Intrusion Set</b>: 1 entries" in summary
    assert "<b>Total Entries</b>: 3" in summary  # identity gak dihitung
    assert "IDENTITY (0 entries)" in text and "No formatter defined for this section." in text
    assert "G-One" in text  # alias grup masuk


def test_sections_follow_the_order_types_first_appear_in_the_bundle() -> None:
    bundle = {"objects": [obj("tool", "t1"), obj("malware", "m1"), obj("tool", "t2")]}

    assert list(build_changes(bundle, now=NOW)) == ["tool", "malware"]


def test_campaign_dates_render_with_and_without_fractions() -> None:
    c = obj("campaign", "Camp", 1, first_seen=ts(30), last_seen=ts(2, fraction=False))

    text, _ = render(build_changes({"objects": [c]}, now=NOW))

    assert "This campaign first seen in 2026-08-27 12:00:00" in text
    assert "This campaign last seen in 2026-09-24 12:00:00" in text
