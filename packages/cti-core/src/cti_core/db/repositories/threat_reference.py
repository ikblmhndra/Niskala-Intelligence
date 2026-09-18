"""Baca (bukan tulis) `threat_actor_groups`/`monitored_people` -- lihat
`db/models/threat_reference.py` buat kenapa dua tabel ini ada dan kenapa
kosong sampai di-seed."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from cti_core.db.models.threat_reference import MonitoredPerson, ThreatActorGroup


def list_threat_actor_groups(session: Session) -> list[str]:
    return sorted(session.execute(select(ThreatActorGroup.name)).scalars().all())


def list_monitored_people(session: Session) -> list[str]:
    return sorted(session.execute(select(MonitoredPerson.name)).scalars().all())
