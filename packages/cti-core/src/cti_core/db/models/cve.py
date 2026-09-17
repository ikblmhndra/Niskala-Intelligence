"""CVE tracker -- gantiin `news_db.cve_tracker` + `cve_false_positives` +
`cve_tickets`. Ditulis dua sisi di sistem lama (scraper `newCveThreat.py`
dkk, web `cve_service.py`) -- lihat plan §1. Multi-tenant lewat `client_id`
(unique bareng `cve_id`), pola yang sama kayak app lama v3.8.0.
"""

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

    cve: Mapped[CveTracker] = relationship(back_populates="pocs")


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
