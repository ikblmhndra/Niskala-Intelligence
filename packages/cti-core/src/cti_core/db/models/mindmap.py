"""Cache mindmap Mermaid -- gantiin `news_db.mindmaps`. Fase 7.3 (router
`mindmap`, Bagian 4).

SATU tabel generik buat SEMUA `feature_type` (`threat_actor`/`cve`/`pir`/
`ransomware`/`newsletter`/`cluster`) -- port apa adanya, kode lama juga
satu collection generik keyed `(feature_type, doc_id)`. `doc_id` TETAP
`String`, bukan `BigInteger`, walau sebagian besar ID sekarang int
(`PIRRequirement.id`, `Newsletter.id`) -- feature_type lain makein STRING
asli (nama TA, `group_name` ransomware, `cve_id`), jadi kolom generik
harus bisa nampung dua-duanya; caller yang nge-`str()`-in ID int
sebelum query/simpen, sama kayak kode lama nge-`str(ObjectId)`."""

from __future__ import annotations

from sqlalchemy import BigInteger, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from cti_core.db.base import Base


class MindmapDoc(Base):
    __tablename__ = "mindmaps"
    __table_args__ = (UniqueConstraint("feature_type", "doc_id", name="uq_mindmap_feature_doc"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    feature_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    doc_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False, default="")
    mermaid_syntax: Mapped[str] = mapped_column(Text, nullable=False, default="")
    custom_syntax: Mapped[str | None] = mapped_column(Text)
    generated_at: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    edited_at: Mapped[str | None] = mapped_column(String(40))
