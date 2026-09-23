"""Port `geopolitical_service.py`. Fase 7.4 Grup A (2026-09-23) --
terima `campaigns` (hasil `cti_api.services.campaign.get_recent_
campaigns()`) sebagai parameter, pure aggregation + 1 batch TA profile
lookup. Backing `GET /api/intelligence/geopolitical`."""

from __future__ import annotations

import datetime
from collections import Counter
from typing import Any

from cti_core.db.repositories.ta import AsyncTAProfileRepo
from sqlalchemy.ext.asyncio import AsyncSession


async def get_geopolitical_summary(
    session: AsyncSession, campaigns: list[dict[str, Any]], *, days: int = 30
) -> dict[str, Any]:
    all_tas: list[str] = []
    for c in campaigns:
        all_tas.extend(c.get("dominant_tas", []))
    unique_tas = list({t for t in all_tas if t})

    rows = await AsyncTAProfileRepo(session).list_profiles_by_names(unique_tas)
    profiles = {row.actor_name.lower(): row.profile for row in rows}

    nation_state_activity: dict[str, dict[str, Any]] = {}
    motivation_counter: Counter[str] = Counter()

    sector_current: Counter[str] = Counter()
    sector_prior: Counter[str] = Counter()
    sector_tas: dict[str, set[str]] = {}

    cutoff_current = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    cutoff_prior = (datetime.date.today() - datetime.timedelta(days=days * 2)).isoformat()

    for c in campaigns:
        c_tas = c.get("dominant_tas", [])
        c_sectors = c.get("dominant_industries", [])
        c_ctrs = c.get("dominant_countries", [])
        cid = c.get("cluster_id", "")
        last_seen = c.get("last_seen", "") or ""

        in_current = last_seen >= cutoff_current
        in_prior = cutoff_prior <= last_seen < cutoff_current

        for sector in c_sectors:
            if not sector:
                continue
            if in_current:
                sector_current[sector] += 1
            elif in_prior:
                sector_prior[sector] += 1
            sector_tas.setdefault(sector, set()).update(t for t in c_tas if t)

        for ta_name in c_tas:
            if not ta_name:
                continue
            profile = profiles.get(ta_name.lower(), {})
            identity = profile.get("identity", {}) or {}
            motivation = profile.get("motivation", {}) or {}

            nation = identity.get("sponsoring_nation") or "Unknown"
            actor_type = identity.get("actor_type", "")
            prim_mot = motivation.get("primary_motivation", "unknown") or "unknown"

            motivation_counter[prim_mot] += 1

            if nation not in nation_state_activity:
                nation_state_activity[nation] = {
                    "campaign_count": 0,
                    "campaigns": [],
                    "primary_motivations": [],
                    "targeted_sectors": [],
                    "targeted_countries": [],
                    "actor_type": actor_type,
                }
            entry = nation_state_activity[nation]
            if cid and cid not in entry["campaigns"]:
                entry["campaigns"].append(cid)
                entry["campaign_count"] += 1
            if prim_mot and prim_mot not in entry["primary_motivations"]:
                entry["primary_motivations"].append(prim_mot)
            for s in c_sectors:
                if s and s not in entry["targeted_sectors"]:
                    entry["targeted_sectors"].append(s)
            for cc in c_ctrs:
                if cc and cc not in entry["targeted_countries"]:
                    entry["targeted_countries"].append(cc)

    all_sectors = set(sector_current.keys()) | set(sector_prior.keys())
    sector_threat_trends: dict[str, dict[str, Any]] = {}
    for sector in all_sectors:
        cur = sector_current.get(sector, 0)
        pri = sector_prior.get(sector, 0)
        if cur > pri:
            trend = "increasing"
        elif cur < pri:
            trend = "decreasing"
        else:
            trend = "stable"
        sector_threat_trends[sector] = {
            "campaign_count": cur,
            "prior_count": pri,
            "threat_actors": sorted(sector_tas.get(sector, set())),
            "trend": trend,
        }

    geopolitical_alerts: list[str] = []

    for nation, entry in nation_state_activity.items():
        if nation == "Unknown":
            continue
        if entry["campaign_count"] >= 3:
            motivations = ", ".join(entry["primary_motivations"][:2]) or "unknown"
            sectors_str = ", ".join(entry["targeted_sectors"][:3])
            msg = (
                f"Nation-state activity: {nation} linked to {entry['campaign_count']} campaign(s) "
                f"({motivations}) targeting {sectors_str or 'multiple sectors'}"
            )
            geopolitical_alerts.append(msg)

    for sector, info in sector_threat_trends.items():
        cur = info["campaign_count"]
        pri = info["prior_count"]
        if info["trend"] == "increasing" and pri > 0:
            pct = round((cur - pri) / pri * 100)
            geopolitical_alerts.append(
                f"Threat activity targeting {sector} increased {pct}% "
                f"({pri} → {cur} campaigns) in last {days} days"
            )
        elif info["trend"] == "increasing" and pri == 0 and cur >= 2:
            geopolitical_alerts.append(
                f"New threat activity targeting {sector}: {cur} campaign(s) "
                f"detected in last {days} days"
            )

    nation_sector: dict[str, Counter[str]] = {}
    for nation, entry in nation_state_activity.items():
        if nation == "Unknown":
            continue
        nation_sector[nation] = Counter(entry["targeted_sectors"])
    for nation, sc in nation_sector.items():
        for sector, count in sc.items():
            if count >= 2:
                geopolitical_alerts.append(
                    f"{nation}-linked actors running {count} converging campaigns "
                    f"targeting {sector}"
                )

    return {
        "nation_state_activity": nation_state_activity,
        "motivation_breakdown": dict(motivation_counter),
        "sector_threat_trends": sector_threat_trends,
        "geopolitical_alerts": geopolitical_alerts,
        "days": days,
        "campaign_count": len(campaigns),
    }
