"""Gantiin `news_db.clusters` -- port `cluster_service.py`'s
`_persist_and_tag()`. Fase 7.4 Grup A (2026-09-23).

**Cuma nampung hasil `get_clusters()`** (TF-IDF greedy clustering,
threshold tunable, persisted -- backing `/api/clusters` + `/clusters/
evolution` + `/clusters/{id}/trends`). `get_recent_campaigns()` (union-
find, threshold beda, jauh lebih kaya field-nya -- severity/diamond
model/kill chain/geopolitical) itu PIPELINE TERPISAH, gak pernah
di-cache/persist di legacy sama sekali (dihitung ulang tiap request) --
gak butuh tabel, lihat `cti_api.services.campaign`.

`daily_counts` JSONB (list `{date, count, new_iocs, new_tas}`, di-slice
90 entry terbaru) -- port apa adanya, dibaca UTUH sekaligus + diolah
Python-side (`campaign_trend_service`), gak pernah di-query per-tanggal
di SQL. Sama pola kayak `CveTracker.cisa_kev_detail`/`PackageDepGraph.
scorecard_checks` (blob deskriptif, bukan field yang perlu index)."""

from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import BigInteger, Date, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from cti_core.db.base import Base, TimestampMixin


class Cluster(TimestampMixin, Base):
    __tablename__ = "clusters"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    cluster_id: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)
    """`sha256(nama_ternormalisasi)[:16]` -- port `_cluster_id()`, deterministic
    dari nama cluster (bukan random), jadi cluster yang sama muncul lagi
    dapet id yang sama."""
    cluster_name: Mapped[str] = mapped_column(Text, nullable=False)

    first_seen: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    last_seen: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    last_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    peak_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    daily_counts: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
