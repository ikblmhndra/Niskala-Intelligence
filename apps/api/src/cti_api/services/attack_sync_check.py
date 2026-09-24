"""Port keputusan "perlu re-sync atau enggak" dari `_attack_sync_loop()`
(`ScraperNewsWeb/app/main.py:151`) -- Fase 7.8, salah satu dari 5 loop
Celery beat.

`AsyncAttackSyncRepo.sync_all_domains()`/`get_sync_status()` sendiri UDAH
diport (Fase 7.3 Bagian 3, dipanggil router `attack`) -- yang belum ada
cuma logika "kapan perlu jalan": re-sync kalau ADA domain yang belum
pernah sync SAMA SEKALI, atau domain TERLAMA yang sync-nya udah lebih
dari `interval_days`. Modul terpisah (bukan langsung di
`cti_worker.tasks.periodic`) biar testable tanpa jaring Celery/beat --
sama alasan `pir_alert`/`ioc_decay` juga modul `cti_api.services`
sendiri."""

from __future__ import annotations

import datetime
from typing import Any

from cti_core.db.repositories.attack import AsyncAttackSyncRepo
from sqlalchemy.ext.asyncio import AsyncSession


def _needs_sync(status: list[dict[str, Any]], *, interval_days: int) -> bool:
    never_synced = any(s.get("status") == "never" for s in status)
    if never_synced:
        return True

    oldest_sync: datetime.datetime | None = None
    for s in status:
        last_sync = s.get("last_sync")
        if not last_sync:
            continue
        dt = datetime.datetime.fromisoformat(last_sync)
        if oldest_sync is None or dt < oldest_sync:
            oldest_sync = dt

    if oldest_sync is None:
        return True
    return (datetime.datetime.now(datetime.UTC) - oldest_sync).days >= interval_days


async def sync_if_needed(
    session: AsyncSession, *, interval_days: int
) -> list[dict[str, Any]] | None:
    """`None` kalau semua domain masih fresh (gak jalan) -- hasil
    `sync_all_domains()` kalau beneran jalan."""
    repo = AsyncAttackSyncRepo(session)
    status = await repo.get_sync_status()
    if not _needs_sync(status, interval_days=interval_days):
        return None
    return await repo.sync_all_domains()
