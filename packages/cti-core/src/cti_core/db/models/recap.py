"""Recap harian -- gantiin `daily_recaps` (Mongo). Fase 7.3 (router
`recap`, Bagian 5). Ringkasan LLM (news+X intel yang masuk hari itu) +
forecast 1-3 hari ke depan, cached per tanggal (`date` unique).

`yesterday`/`forecast`/`counts`/`token_usage` JSONB -- output LLM
terstruktur + metadata pemanggilan, "cair" persis alasan yang sama kayak
`Newsletter.sections`/`PIRRequirement.criteria` (bag hasil LLM/ad hoc,
bukan entitas relasional yang perlu di-query per field)."""

from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from cti_core.db.base import Base


class DailyRecap(Base):
    __tablename__ = "daily_recaps"
    __table_args__ = (UniqueConstraint("date", name="uq_daily_recap_date"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(String(10), nullable=False)
    """`YYYY-MM-DD` -- string, bukan `Date`, konsisten sama gimana
    `recap_service.py` lama nge-treat tanggal ini di mana-mana (kunci
    lookup `daily_recaps`, bukan field yang di-range-query)."""
    headline: Mapped[str] = mapped_column(Text, nullable=False, default="")
    yesterday: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    forecast: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    counts: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    generated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    model: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    token_usage: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    raw_llm: Mapped[str | None] = mapped_column(Text)
    """Diisi cuma kalau parsing JSON dari LLM gagal (`_extract_json`
    fallback `{"_raw": raw}`) -- port apa adanya, audit trail buat
    kegagalan parsing, `None` di jalur normal."""
