"""Data referensi buat filter IOC -- gantiin `news_db.ioc_allowlist` dan
`news_db.threat_feeds` (Mongo). Pola "web kurasi, scraper patuh" KEEMPAT
(lihat `techstack.py`, `tweet.py::MonitoredAccount`) -- disebut plan §8.3
sebagai tiga yang udah kebukti, `ioc_allowlist` yang belum sempat ke-port
pas Fase 2/4 karena baru kepake di Fase 5 (`cti_enrich.stages.extract_iocs`).

`ThreatFeedEntry` nampung C2 IP/domain dari feed eksternal (`deepdarkCTI`,
lihat `nlp.py::_check_c2_hit` lama) -- tabelnya dibangun di sini duluan
(dipakai `stages/score.py` buat `Article.c2_indicator`) SEBELUM scraper yang
nulis ke situ (`deepdarkCTI`) sendiri di-port -- simetris sama
`malware_trends` (Fase 4: tabel + sink duluan, `any_run_trends.py` penulis
pertamanya)."""

from __future__ import annotations

from sqlalchemy import BigInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from cti_core.db.base import Base, TimestampMixin


class IocAllowlistEntry(TimestampMixin, Base):
    __tablename__ = "ioc_allowlist_entries"
    __table_args__ = (UniqueConstraint("type", "value", name="uq_ioc_allowlist_type_value"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    """url_domain | email_domain | ip -- persis 3 tipe yang dibaca
    `iocExtractor._get_allowlist()`/`_filter_iocs()` lama."""
    value: Mapped[str] = mapped_column(String(300), nullable=False)
    note: Mapped[str | None] = mapped_column(String(300))


class ThreatFeedEntry(TimestampMixin, Base):
    __tablename__ = "threat_feed_entries"
    __table_args__ = (UniqueConstraint("feed", "type", "value", name="uq_threat_feed_entry"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    feed: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    """Nama feed sumber, mis. "deepdarkcti_c2" -- string bukan enum, tabel
    ini generik buat feed C2 apa pun, gak cuma deepdarkCTI (sama alasan
    `MalwareTrend.source` string bebas, lihat Fase 4)."""
    type: Mapped[str] = mapped_column(String(10), nullable=False)
    """ip | domain."""
    value: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
