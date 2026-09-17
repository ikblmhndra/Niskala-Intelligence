"""Auth, RBAC, multi-tenant -- gantiin `users`/`roles`/`clients`/`audit_log`.

`client_id` dipakai sebagai PRIMARY KEY string (bukan surrogate int) karena
dia udah jadi natural key yang direferensikan banyak tabel lain (cve_tracker,
dst) di sistem lama -- lihat CveTracker.client_id.

31 permission (`ALL_PERMISSIONS` di app lama, role_service.py) tetap jadi
konstanta Python di layer service (Fase 7), BUKAN tabel terpisah di sini --
itu closed enumeration yang di-enforce di kode, disimpan di `Role.permissions`
sebagai JSONB list. Kalau nanti butuh query "role mana yang punya permission
X", baru dipertimbangin jadi tabel join.
"""

from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cti_core.db.base import Base, TimestampMixin


class Client(TimestampMixin, Base):
    """Tenant. `client_id` PK -- natural key, direferensikan tabel lain."""

    __tablename__ = "clients"

    client_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    countries: Mapped[list[ClientCountry]] = relationship(
        back_populates="client", cascade="all, delete-orphan", lazy="selectin"
    )


class ClientCountry(Base):
    __tablename__ = "client_countries"
    __table_args__ = (UniqueConstraint("client_id", "country_code", name="uq_client_country"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    client_id: Mapped[str] = mapped_column(
        ForeignKey("clients.client_id", ondelete="CASCADE"), nullable=False
    )
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)

    client: Mapped[Client] = relationship(back_populates="countries")


class Role(Base):
    """System role (superadmin/admin/analyst, di-seed startup) atau custom."""

    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(50), primary_key=True)
    permissions: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(200), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role_name: Mapped[str] = mapped_column(ForeignKey("roles.name"), nullable=False)
    force_pw_change: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_sign_in: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))

    role: Mapped[Role] = relationship()
    clients: Mapped[list[UserClient]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )


class UserClient(Base):
    """Satu user bisa akses banyak client (multi-tenant, v3.8.0 di app
    lama). Gantiin `client_ids: list` di dokumen user Mongo."""

    __tablename__ = "user_clients"
    __table_args__ = (UniqueConstraint("user_id", "client_id", name="uq_user_client"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    client_id: Mapped[str] = mapped_column(
        ForeignKey("clients.client_id", ondelete="CASCADE"), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="clients")


class AuditLogEntry(Base):
    """Gantiin `audit_log`. Sengaja gak FK ke users.id -- log harus tetap
    kebaca walau user-nya udah dihapus."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
