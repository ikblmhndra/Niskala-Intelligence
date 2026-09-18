"""Port `ScraperNewsWeb/app/services/d3fend_service.py` -- proxy+cache ke
API publik D3FEND (`d3fend.mitre.org`). `urllib.request` sync-in-thread
lama diganti `httpx.AsyncClient`, konsisten sama cara `apps/api`/
`cti_enrich` manggil HTTP eksternal lain -- perilaku sama persis
(timeout 10s, cache in-memory per proses, gagal -> list kosong), cuma
mekanisme HTTP-nya yang disamain ke konvensi baru."""

from __future__ import annotations

from typing import Any

import httpx

_cache: dict[str, list[dict[str, str]]] = {}


async def get_d3fend_countermeasures(technique_id: str) -> list[dict[str, str]]:
    tid = technique_id.upper()
    if tid in _cache:
        return _cache[tid]

    url_id = tid.replace(".", "/")
    url = f"https://d3fend.mitre.org/api/offensive-technique/attack/{url_id}.json"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers={"Accept": "application/json"})
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
    except Exception as e:
        print(f"[D3FEND] Lookup failed for {tid}: {e}")
        return []

    bindings = data.get("off_to_def", {}).get("results", {}).get("bindings", [])
    seen: set[str] = set()
    techniques: list[dict[str, str]] = []
    for b in bindings:
        name = b.get("def_tech_label", {}).get("value", "")
        owl_uri = b.get("def_tech", {}).get("value", "")
        d3f_class = owl_uri.split("#")[-1] if "#" in owl_uri else ""
        d3f_id = b.get("def_tech_id", {}).get("value", d3f_class)
        artifact = b.get("def_artifact_label", {}).get("value", "")
        tactic = b.get("def_tactic_label", {}).get("value", "")
        if name and name not in seen:
            seen.add(name)
            techniques.append(
                {
                    "id": d3f_id,
                    "name": name,
                    "tactic": tactic,
                    "artifact": artifact,
                    "url": f"https://d3fend.mitre.org/technique/d3f:{d3f_class}"
                    if d3f_class
                    else "https://d3fend.mitre.org",
                }
            )
    _cache[tid] = techniques
    return techniques
