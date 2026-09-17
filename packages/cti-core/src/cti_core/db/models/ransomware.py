"""Korban ransomware -- gantiin `news_db.ransomware_victims`. Cuma ditulis
scraper (`ransomwareLiveThreat.py` / `RansomwareLive` collector Fase 3),
web cuma baca -- salah satu dari sedikit collection yang gak dual-write
di sistem lama.
"""

from __future__ import annotations

import datetime

from sqlalchemy import BigInteger, Date, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from cti_core.db.base import Base, TimestampMixin


class RansomwareVictim(TimestampMixin, Base):
    __tablename__ = "ransomware_victims"
    __table_args__ = (UniqueConstraint("offset_key", name="uq_ransomware_offset_key"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    offset_key: Mapped[str] = mapped_column(String(600), nullable=False)
    """f"{group_name}:{victim}:{country_code}:{published}" -- dedup key,
    dari RansomwareVictimItem.dedup_key() (Fase 3). Bukan url_hash biasa
    karena sumbernya (API snapshot bulanan) gak punya URL per-korban yang
    stabil."""

    group_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    victim: Mapped[str] = mapped_column(String(500), nullable=False)
    domain: Mapped[str | None] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    country_code: Mapped[str | None] = mapped_column(String(2), index=True)
    industry: Mapped[str | None] = mapped_column(String(150))
    published: Mapped[datetime.date | None] = mapped_column(Date)
    discovered: Mapped[datetime.date | None] = mapped_column(Date)
    post_url: Mapped[str] = mapped_column(Text, nullable=False, default="Unknown")
    ransom: Mapped[str | None] = mapped_column(Text)
    data_size: Mapped[str | None] = mapped_column(Text)
    screenshot: Mapped[str | None] = mapped_column(Text)
