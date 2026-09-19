"""CVE tracker -- gantiin `news_db.cve_tracker` + `cve_false_positives` +
`cve_tickets`. Ditulis dua sisi di sistem lama (scraper `newCveThreat.py`
dkk, web `cve_service.py`) -- lihat plan §1. Multi-tenant lewat `client_id`
(unique bareng `cve_id`), pola yang sama kayak app lama v3.8.0.

`cisa_kev`/`active_exploitation`/`threat_actors`/`ttps` (Fase 7.3, router
`crossref`, Bagian 3) -- field ini ADA di dokumen Mongo `cve_tracker`
lama, tapi ditulis loop enrichment CVE (`app/main.py::_cve_enrichment_loop`,
proses cross-reference CVE vs CISA KEV + artikel/TA) yang BELUM diport --
itu salah satu dari 5 loop yang dipindah ke Celery beat (Fase 7.8, lihat
docs/PROGRESS.md). Kolomnya ditambah SEKARANG (gap ketauan pas porting
`crossref`, pola sama kayak nambah kolom pas nemu gap di router lain)
supaya query `crossref` BENER begitu 7.8 ngisi datanya -- buat sekarang
kolomnya bakal selalu kosong/false, bukan bug, cuma cold-start yang sama
kayak `techstack` sebelum seed. `threat_actors`/`ttps` dinormalisasi jadi
tabel anak (`CveThreatActor`/`CveTTP`), sama pola kayak
`ArticleThreatActor`/`ArticleTTP` -- `crossref` butuh set-intersection
per-value (`pir_ttps & cve_ttps`), bukan sekadar baca utuh.

`CveNewsletterMention` (Fase 7.3, router `newsletter`, Bagian 4) --
gantiin `cve_tracker.newsletter_mentions` (array Mongo, `$push` dedup by
url). Ini DITULIS sama fitur yang lagi diport sendiri (newsletter), beda
dari `cisa_kev`/`threat_actors` dkk di atas yang nunggu loop terpisah."""

from __future__ import annotations

import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cti_core.db.base import Base, TimestampMixin


class CveTracker(TimestampMixin, Base):
    __tablename__ = "cve_tracker"
    __table_args__ = (UniqueConstraint("cve_id", "client_id", name="uq_cve_tracker_cve_client"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    cve_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    client_id: Mapped[str] = mapped_column(
        ForeignKey("clients.client_id", ondelete="CASCADE"), nullable=False, index=True
    )
    tech: Mapped[str | None] = mapped_column(String(200))
    link: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    published: Mapped[datetime.date | None] = mapped_column(Date)
    solutions: Mapped[str | None] = mapped_column(Text)

    cve_score: Mapped[float | None] = mapped_column(Float)
    cve_severity: Mapped[str | None] = mapped_column(String(20))
    cvss_vector: Mapped[str | None] = mapped_column(String(100))
    cve_modified_date: Mapped[datetime.date | None] = mapped_column(Date)

    poc_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cisa_kev: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active_exploitation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    detected_on: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    registered_date: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))

    references: Mapped[list[CveReference]] = relationship(
        back_populates="cve", cascade="all, delete-orphan", lazy="selectin"
    )
    affected: Mapped[list[CveAffected]] = relationship(
        back_populates="cve", cascade="all, delete-orphan", lazy="selectin"
    )
    pocs: Mapped[list[CvePoc]] = relationship(
        back_populates="cve", cascade="all, delete-orphan", lazy="selectin"
    )
    threat_actors: Mapped[list[CveThreatActor]] = relationship(
        back_populates="cve", cascade="all, delete-orphan", lazy="selectin"
    )
    ttps: Mapped[list[CveTTP]] = relationship(
        back_populates="cve", cascade="all, delete-orphan", lazy="selectin"
    )
    newsletter_mentions: Mapped[list[CveNewsletterMention]] = relationship(
        back_populates="cve", cascade="all, delete-orphan", lazy="selectin"
    )


class CveReference(Base):
    __tablename__ = "cve_references"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    cve_tracker_id: Mapped[int] = mapped_column(
        ForeignKey("cve_tracker.id", ondelete="CASCADE"), nullable=False
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)

    cve: Mapped[CveTracker] = relationship(back_populates="references")


class CveAffected(Base):
    __tablename__ = "cve_affected"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    cve_tracker_id: Mapped[int] = mapped_column(
        ForeignKey("cve_tracker.id", ondelete="CASCADE"), nullable=False
    )
    affected: Mapped[str] = mapped_column(String(300), nullable=False)

    cve: Mapped[CveTracker] = relationship(back_populates="affected")


class CvePoc(Base):
    __tablename__ = "cve_pocs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    cve_tracker_id: Mapped[int] = mapped_column(
        ForeignKey("cve_tracker.id", ondelete="CASCADE"), nullable=False
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str | None] = mapped_column(String(100))
    poc_type: Mapped[str | None] = mapped_column(String(20))
    """"poc" atau "exploit" -- klasifikasi regex sederhana atas nama/deskripsi
    repo (lihat `githubPOCMonitor.py` lama, `github_poc_monitor.py` baru).
    Kolom ketinggalan pas Fase 2 (model ini ditulis SEBELUM `githubPOCMonitor.py`
    beneran di-port, jadi belum ketauan field ini dipakai) -- ditambah Fase 4
    pas port beneran butuh, bukan dirombak ulang."""

    cve: Mapped[CveTracker] = relationship(back_populates="pocs")


class CveNewsletterMention(Base):
    __tablename__ = "cve_newsletter_mentions"
    __table_args__ = (UniqueConstraint("cve_tracker_id", "url", name="uq_cve_newsletter_mention"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    cve_tracker_id: Mapped[int] = mapped_column(
        ForeignKey("cve_tracker.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False, default="")
    url: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    mention_date: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    added_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    cve: Mapped[CveTracker] = relationship(back_populates="newsletter_mentions")


class CveThreatActor(Base):
    __tablename__ = "cve_threat_actors"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    cve_tracker_id: Mapped[int] = mapped_column(
        ForeignKey("cve_tracker.id", ondelete="CASCADE"), nullable=False
    )
    threat_actor: Mapped[str] = mapped_column(String(200), nullable=False, index=True)

    cve: Mapped[CveTracker] = relationship(back_populates="threat_actors")


class CveTTP(Base):
    __tablename__ = "cve_ttps"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    cve_tracker_id: Mapped[int] = mapped_column(
        ForeignKey("cve_tracker.id", ondelete="CASCADE"), nullable=False
    )
    ttp_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    ttp_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")

    cve: Mapped[CveTracker] = relationship(back_populates="ttps")


class CveFalsePositive(Base):
    __tablename__ = "cve_false_positives"
    __table_args__ = (UniqueConstraint("cve_id", "client_id", name="uq_cve_fp_cve_client"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    cve_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    client_id: Mapped[str] = mapped_column(
        ForeignKey("clients.client_id", ondelete="CASCADE"), nullable=False
    )
    marked_by: Mapped[str | None] = mapped_column(String(200))
    marked_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CveTicket(TimestampMixin, Base):
    __tablename__ = "cve_tickets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="open")

    cve_ids: Mapped[list[CveTicketItem]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan", lazy="selectin"
    )


class CveTicketItem(Base):
    __tablename__ = "cve_ticket_items"
    __table_args__ = (UniqueConstraint("ticket_id", "cve_id", name="uq_cve_ticket_item"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("cve_tickets.id", ondelete="CASCADE"), nullable=False
    )
    cve_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    ticket: Mapped[CveTicket] = relationship(back_populates="cve_ids")
