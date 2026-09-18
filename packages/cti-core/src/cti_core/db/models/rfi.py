"""RFI (Request For Information) tracker -- gantiin `threatintel.
rfi_requests` (Mongo). Bagian 2 (survei 21 router sisa, docs/PROGRESS.md)
-- domain baru self-contained, CRUD murni lewat web, gak ada scraper/
enrichment yang nulis ke sini.

`linked_pir` kode lama cuma string ObjectId LEPAS, gak ada foreign key
beneran (Mongo gak validasi referensi). Di sini jadi FK asli ke
`pir_requirements.id` (`ondelete="SET NULL"` -- PIR yang dihapus gak ikut
ngehapus RFI, cuma link-nya putus) -- port pola `str -> int PK + FK asli`
yang sama kayak semua entity lain (Article.id, TechStackEntry.id, dst),
bukan keputusan baru di sini."""

from __future__ import annotations

import datetime

from sqlalchemy import BigInteger, Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from cti_core.db.base import Base, TimestampMixin


class RFIRequest(TimestampMixin, Base):
    __tablename__ = "rfi_requests"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    requester: Mapped[str] = mapped_column(String(200), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    due_date: Mapped[datetime.date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    """open | in_progress | closed -- port apa adanya, gak divalidasi
    DB-level (CHECK constraint), sama kayak kode lama yang cuma string
    bebas."""
    linked_pir_id: Mapped[int | None] = mapped_column(
        ForeignKey("pir_requirements.id", ondelete="SET NULL")
    )
    response: Mapped[str] = mapped_column(Text, nullable=False, default="")
    client_id: Mapped[str] = mapped_column(
        ForeignKey("clients.client_id", ondelete="CASCADE"), nullable=False, index=True
    )
