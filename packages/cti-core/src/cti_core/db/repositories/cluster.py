"""`AsyncClusterRepo` -- satu-satunya jalur baca/tulis `clusters`. Port
`cluster_service.py`'s `_persist_and_tag()`/`_ensure_clusters_index()`
(Mongo upsert + `$max`/`$push $slice` -90) + `campaign_trend_service.py`'s
baca `CLUSTERS_COLLECTION`. Fase 7.4 Grup A (2026-09-23)."""

from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cti_core.db.models.cluster import Cluster

_DAILY_COUNTS_KEEP = 90


class AsyncClusterRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_cluster_id(self, cluster_id: str) -> Cluster | None:
        result = await self.session.execute(select(Cluster).where(Cluster.cluster_id == cluster_id))
        return result.scalar_one_or_none()

    async def list_seen_since(self, cutoff: datetime.date) -> list[Cluster]:
        """Port `get_campaign_evolution()`'s query -- `last_seen >= cutoff`."""
        result = await self.session.execute(
            select(Cluster).where(Cluster.last_seen >= cutoff).limit(500)
        )
        return list(result.scalars().all())

    async def upsert_and_tag(self, clusters: list[dict[str, Any]], *, today: datetime.date) -> None:
        """Port `_persist_and_tag()` -- upsert tiap cluster (nama/last_seen/
        last_count `$set`, `peak_count` `$max`, `daily_counts` `$push` +
        slice -90), lalu SET `c["re_emerged"]` in-place di tiap dict input
        (cluster yang `last_seen` LAMA-nya > 7 hari lalu dari sekarang).
        `today` diterima sebagai parameter (bukan `datetime.utcnow()`
        internal) biar gampang dites deterministik.

        `new_iocs`/`new_tas` di `daily_counts` SELALU 0 -- port apa
        adanya, `_compute_clusters()` legacy sendiri gak pernah ngisi
        dua key ini di dict cluster yang dikirim ke sini (bukan bug baru
        dari porting, field mati di kode lama)."""
        dormant_cutoff = today - datetime.timedelta(days=7)

        ids = [c["cluster_id"] for c in clusters]
        existing_result = await self.session.execute(
            select(Cluster).where(Cluster.cluster_id.in_(ids))
        )
        existing_by_id = {row.cluster_id: row for row in existing_result.scalars().all()}

        for c in clusters:
            cid = c["cluster_id"]
            row = existing_by_id.get(cid)
            re_emerged = row is not None and row.last_seen < dormant_cutoff

            new_iocs = c.get("new_iocs", [])
            new_tas = c.get("new_tas", [])
            daily_entry = {
                "date": today.isoformat(),
                "count": c["article_count"],
                "new_iocs": len(new_iocs) if isinstance(new_iocs, list) else 0,
                "new_tas": len(new_tas) if isinstance(new_tas, list) else 0,
            }

            if row is None:
                row = Cluster(
                    cluster_id=cid,
                    cluster_name=c["cluster_name"],
                    first_seen=today,
                    last_seen=today,
                    last_count=c["article_count"],
                    peak_count=c["article_count"],
                    daily_counts=[daily_entry],
                )
                self.session.add(row)
            else:
                row.cluster_name = c["cluster_name"]
                row.last_seen = today
                row.last_count = c["article_count"]
                row.peak_count = max(row.peak_count, c["article_count"])
                row.daily_counts = [*row.daily_counts, daily_entry][-_DAILY_COUNTS_KEEP:]

            c["re_emerged"] = re_emerged

        await self.session.flush()
