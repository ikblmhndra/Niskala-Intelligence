"""Changelog rilis MITRE ATT&CK dari bundle STIX -- port `mitreValidator.
mitreJsonURL()` + `mitreUpdateLog()` (`ScraperNews/modules/mitreValidator.py`).

FUNGSI MURNI: masuk bundle (dict) + waktu sekarang, keluar teks. Skrip lama
mencampur unduh HTTP, tulis file, dan format dalam satu modul; di sini
pengunduhan ada di scraper (`mitre_github.py`) dan pengiriman di sink.

Yang dipertahankan: jendela 7 hari atas `created` (objek yang dibuat lebih dari
7 hari sebelum commit rilis TIDAK masuk changelog -- itu perilaku lama, apa adanya),
tipe `x-mitre-data-component` dilewati, objek `revoked` dilewati, urutan seksi =
urutan tipe pertama kali muncul di bundle.

Yang diperbaiki (semua bug di kode lama, bukan perubahan desain):
  - `strftime("%d-%m-%Y %H:%M%:%S")` -> `%:` bukan directive valid; cetakannya
    `12:30%:45`. Field itu sebenarnya gak dipakai formatter mana pun, jadi
    dibuang.
  - `data["description"]`/`data["x_mitre_domains"]`/... langsung -> `KeyError`
    membatalkan SELURUH changelog kalau satu objek gak punya field itu.
    Sekarang `.get()` dengan default kosong.
  - `_format_attack_pattern` baca `item["parent_tech_id"]` padahal kuncinya
    `parent_technique_id` -> blok "This technique has a parent" gak pernah
    muncul, sedangkan baris "has a parent: ()" tercetak KOSONG buat teknik
    non-sub. Sekarang muncul hanya untuk sub-teknik.
  - Nama sumber/target relationship dicari dengan loop O(n*m) atas seluruh
    bundle (puluhan ribu objek); sekarang indeks `id -> name` sekali.
  - Timestamp `first_seen`/`last_seen` kampanye crash kalau tanpa fraksi detik.
"""

from __future__ import annotations

import datetime
import html
from collections.abc import Callable
from typing import Any

WINDOW_DAYS = 7
_SKIP_TYPES = {"x-mitre-data-component"}
_SEP = " || "


def _parse_ts(raw: str) -> datetime.datetime | None:
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.datetime.strptime(raw, fmt)
        except (ValueError, TypeError):
            continue
    return None


def _join(values: Any) -> str:
    return _SEP.join(str(v) for v in values) if isinstance(values, list) else ""


def _mitre_ref(obj: dict[str, Any]) -> tuple[str, str]:
    """(external_id, url) dari referensi `mitre-attack`; yang TERAKHIR menang
    (sama dengan loop lama yang menimpa variabel tiap ketemu)."""
    ext_id = url = ""
    for ref in obj.get("external_references", []):
        if ref.get("source_name") == "mitre-attack":
            ext_id, url = ref.get("external_id", ""), ref.get("url", "")
    return ext_id, url


def _base(obj: dict[str, Any], prefix: str) -> dict[str, str]:
    ext_id, url = _mitre_ref(obj)
    return {
        f"{prefix}_name": obj.get("name", ""),
        f"{prefix}_desc": obj.get("description", ""),
        f"{prefix}_id": ext_id,
        f"{prefix}_url": url,
    }


def _attack_pattern(obj: dict[str, Any], by_tech_id: dict[str, dict[str, Any]]) -> dict[str, str]:
    row = {
        "tech_id": "",
        "tech_name": obj.get("name", ""),
        "tech_url": "",
        "tech_desc": obj.get("description", ""),
        "parent_technique_id": "",
        "parent_technique_name": "",
        "parent_technique_url": "",
        "parent_technique_desc": "",
        "kill_chain": _SEP.join(
            p["phase_name"]
            for p in obj.get("kill_chain_phases", [])
            if p.get("kill_chain_name") == "mitre-attack"
        ),
        "affected_platform": _join(obj.get("x_mitre_platforms")),
        "data_sources": _join(obj.get("x_mitre_data_sources")),
        "ttp_domain": _join(obj.get("x_mitre_domains")),
    }
    row["tech_id"], row["tech_url"] = _mitre_ref(obj)
    if obj.get("x_mitre_is_subtechnique") is True:
        row["parent_technique_id"] = row["tech_id"].split(".")[0]
        parent = by_tech_id.get(row["parent_technique_id"])
        if parent is not None:
            row["parent_technique_name"] = parent.get("name", "")
            row["parent_technique_desc"] = parent.get("description", "")
            row["parent_technique_url"] = _mitre_ref(parent)[1]
    return row


def _software(obj: dict[str, Any]) -> dict[str, str]:
    return {
        **_base(obj, "software"),
        "affected_platform": _join(obj.get("x_mitre_platforms")),
        "software_domain": _join(obj.get("x_mitre_domains")),
        "software_aliases": _join(obj.get("x_mitre_aliases")),
    }


def _intrusion_set(obj: dict[str, Any]) -> dict[str, str]:
    return {
        **_base(obj, "group"),
        "group_domain": _join(obj.get("x_mitre_domains")),
        "group_aliases": _join(obj.get("aliases")),
    }


def _campaign(obj: dict[str, Any]) -> dict[str, str]:
    return {
        **_base(obj, "campaign"),
        "campaign_first_seen": obj.get("first_seen", ""),
        "campaign_last_seen": obj.get("last_seen", ""),
        "campaign_domain": _join(obj.get("x_mitre_domains")),
        "campaign_aliases": _join(obj.get("aliases")),
    }


def _tactic(obj: dict[str, Any]) -> dict[str, str]:
    return {**_base(obj, "tactic"), "tactic_domain": _join(obj.get("x_mitre_domains"))}


def _mitigation(obj: dict[str, Any]) -> dict[str, str]:
    return {**_base(obj, "mitigation"), "mitigation_domain": _join(obj.get("x_mitre_domains"))}


def _data_source(obj: dict[str, Any]) -> dict[str, str]:
    return {
        **_base(obj, "data_source"),
        "data_source_platforms_string": _join(obj.get("x_mitre_platforms")),
        "data_source_domain": _join(obj.get("x_mitre_domains")),
        "collection_layers": _join(obj.get("x_mitre_collection_layers")),
    }


def build_changes(
    bundle: dict[str, Any], *, now: datetime.datetime, window_days: int = WINDOW_DAYS
) -> dict[str, list[dict[str, str]]]:
    """`{tipe_objek: [baris, ...]}` untuk objek yang dibuat dalam `window_days`."""
    objects: list[dict[str, Any]] = bundle.get("objects", [])
    names = {o["id"]: o.get("name", "") for o in objects if "id" in o}
    by_tech_id = {
        _mitre_ref(o)[0]: o
        for o in objects
        if o.get("type") == "attack-pattern" and _mitre_ref(o)[0]
    }

    simple: dict[str, Callable[[dict[str, Any]], dict[str, str]]] = {
        "malware": _software,
        "tool": _software,
        "intrusion-set": _intrusion_set,
        "campaign": _campaign,
        "x-mitre-tactic": _tactic,
        "course-of-action": _mitigation,
        "x-mitre-data-source": _data_source,
    }

    changes: dict[str, list[dict[str, str]]] = {}
    for obj in objects:
        if obj.get("revoked") is True:
            continue
        created = _parse_ts(obj.get("created", ""))
        if created is None or (now - created).days > window_days:
            continue
        kind = obj.get("type", "")
        if kind in _SKIP_TYPES:
            continue

        if kind == "attack-pattern":
            row = _attack_pattern(obj, by_tech_id)
        elif kind == "relationship":
            row = {
                "source_ref_id": obj.get("source_ref", ""),
                "source_ref_name": names.get(obj.get("source_ref", ""), ""),
                "target_ref_id": obj.get("target_ref", ""),
                "target_ref_name": names.get(obj.get("target_ref", ""), ""),
                "relationship_type": obj.get("relationship_type", ""),
                "desc": obj.get("description", ""),
            }
        elif kind in simple:
            row = simple[kind](obj)
        else:
            changes.setdefault(kind, [])  # seksi muncul (0 entri), persis perilaku lama
            continue
        changes.setdefault(kind, []).append(row)
    return changes


def _fmt_time(raw: str) -> str:
    parsed = _parse_ts(raw)
    return parsed.strftime("%Y-%m-%d %H:%M:%S") if parsed else raw


def _f_mitigation(i: dict[str, str]) -> str:
    return (
        f"----- {i['mitigation_name']} ({i['mitigation_id']}) -----\n"
        f"{i['mitigation_url']}\n{i['mitigation_desc']}\n\n"
        f"This mitigation applicable in:\n{i['mitigation_domain']}\n"
    )


def _f_software(kind: str) -> Callable[[dict[str, str]], str]:
    def fmt(i: dict[str, str]) -> str:
        return (
            f"----- {i['software_name']} ({i['software_aliases']}/{i['software_id']}) -----\n"
            f"{i['software_url']}\n{i['software_desc']}\n\n"
            f"Affected plaftorm of this {kind} is:\n{i['affected_platform']}\n\n"
            f"This {kind} applicable in:\n{i['software_domain']}\n"
        )

    return fmt


def _f_attack_pattern(i: dict[str, str]) -> str:
    slug = i["tech_id"].replace(".", "/")
    text = (
        f"----- {i['tech_name']} ({i['tech_id']}) -----\n"
        f"https://attack.mitre.org/techniques/{slug}\n{i['tech_desc']}\n\n"
        f"This technique's attack chain is:\n{i['kill_chain']}\n\n"
        f"Affected plaftorm of this techniques is:\n{i['affected_platform']}\n\n"
        f"This technique applicable in:\n{i['ttp_domain']}\n\n"
        f"To detect this technique, consider to logging from {i['data_sources']}\n"
    )
    if i["parent_technique_id"] and i["parent_technique_name"]:
        parent_slug = i["parent_technique_id"].replace(".", "/")
        text += (
            f"\nThis technique has a parent, {i['parent_technique_name']} "
            f"({i['parent_technique_id']}) https://attack.mitre.org/techniques/{parent_slug}\n"
        )
    return text


def _f_campaign(i: dict[str, str]) -> str:
    return (
        f"----- {i['campaign_name']} ({i['campaign_aliases']}/{i['campaign_id']}) -----\n"
        f"{i['campaign_url']}\n{i['campaign_desc']}\n\n"
        f"This campaign first seen in {_fmt_time(i['campaign_first_seen'])}\n"
        f"This campaign last seen in {_fmt_time(i['campaign_last_seen'])}\n\n"
        f"This campaign applicable in:\n{i['campaign_domain']}\n"
    )


def _f_intrusion_set(i: dict[str, str]) -> str:
    return (
        f"----- {i['group_name']} ({i['group_aliases']}/{i['group_id']}) -----\n"
        f"{i['group_url']}\n{i['group_desc']}\n\n"
        f"This intrusion group applicable in:\n{i['group_domain']}\n"
    )


def _f_relationship(i: dict[str, str]) -> str:
    return (
        f"----- {i['source_ref_name']} ({i['source_ref_id']}) -----\n{i['desc']}\n\n"
        f"Have relation with : {i['target_ref_name']} ({i['target_ref_id']})\n"
        f"Relation type : {i['relationship_type']}\n"
    )


_FORMATTERS: dict[str, Callable[[dict[str, str]], str]] = {
    "course-of-action": _f_mitigation,
    "malware": _f_software("Malware"),
    "tool": _f_software("Tool"),
    "attack-pattern": _f_attack_pattern,
    "campaign": _f_campaign,
    "intrusion-set": _f_intrusion_set,
    "relationship": _f_relationship,
}

_SUMMARY_LABELS = (
    ("course-of-action", "Course of Action"),
    ("malware", "Malware"),
    ("tool", "Tool"),
    ("attack-pattern", "Attack Pattern"),
    ("campaign", "Campaign"),
    ("intrusion-set", "Intrusion Set"),
    ("relationship", "Relationship"),
)


def render(changes: dict[str, list[dict[str, str]]]) -> tuple[str, str]:
    """(isi file changelog, ringkasan HTML buat caption Telegram)."""
    lines: list[str] = []
    for section, entries in changes.items():
        lines.append(f"\n{'=' * 80}\n{section.upper()} ({len(entries)} entries)\n{'=' * 80}\n")
        formatter = _FORMATTERS.get(section)
        if formatter is None:
            lines.append("No formatter defined for this section.\n")
            continue
        lines.extend(formatter(entry) + "\n" for entry in entries)

    counts = [(label, len(changes.get(kind, []))) for kind, label in _SUMMARY_LABELS]
    summary = "<b>Changelog</b>:\n" + "\n".join(
        f"    <b>{html.escape(label)}</b>: {n} entries" for label, n in counts
    )
    summary += f"\n    <b>Total Entries</b>: {sum(n for _, n in counts)}"
    return "\n".join(lines), summary
