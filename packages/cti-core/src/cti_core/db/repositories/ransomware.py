"""RansomwareVictimRepo -- upsert ke `ransomware_victims`. Key dedup
`offset_key`, BUKAN url_hash biasa -- sumbernya API snapshot bulanan tanpa
URL stabil per korban (lihat model & RansomwareVictimItem)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from cti_core.db.models.ransomware import RansomwareVictim

_IDENTITY_FIELDS = frozenset({"id", "offset_key", "created_at"})


class RansomwareVictimRepo:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert(self, *, offset_key: str, **fields: Any) -> RansomwareVictim:
        for k in fields:
            if k in _IDENTITY_FIELDS:
                raise ValueError(f"'{k}' itu field identitas, upsert() gak boleh nimpa ini")

        existing = self.session.execute(
            select(RansomwareVictim).where(RansomwareVictim.offset_key == offset_key)
        ).scalar_one_or_none()

        if existing is None:
            victim = RansomwareVictim(offset_key=offset_key, **fields)
            self.session.add(victim)
            self.session.flush()
            return victim

        for k, v in fields.items():
            setattr(existing, k, v)
        self.session.flush()
        return existing

    def get(self, offset_key: str) -> RansomwareVictim | None:
        return self.session.execute(
            select(RansomwareVictim).where(RansomwareVictim.offset_key == offset_key)
        ).scalar_one_or_none()
