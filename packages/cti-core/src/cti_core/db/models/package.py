"""Package vulnerability scanning -- gantiin `monitored_packages` +
`package_vulns` + `package_dep_graph`.

Fitur ini dibangun DUA kali di sistem lama (`app/services/pkg_vuln_service.py`
1109 baris osv.dev/deps.dev vs `ScraperNews/pkgVulnScanner.py` 419 baris +
`techstackNPM.py`) -- 1528 baris buat satu fitur. Skema ini SATU-SATUNYA
representasi; layer service yang lebih lengkap (pkg_vuln_service) yang
diporting (plan §6, Fase 7), implementasi scraper dibuang.
"""

from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cti_core.db.base import Base, TimestampMixin


class MonitoredPackage(TimestampMixin, Base):
    __tablename__ = "monitored_packages"
    __table_args__ = (
        UniqueConstraint("name", "ecosystem", "client_id", name="uq_monitored_package"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    ecosystem: Mapped[str] = mapped_column(String(30), nullable=False)
    """npm | pypi | go | dst."""
    version: Mapped[str | None] = mapped_column(String(100))
    client_id: Mapped[str] = mapped_column(
        ForeignKey("clients.client_id", ondelete="CASCADE"), nullable=False, index=True
    )

    vulns: Mapped[list[PackageVuln]] = relationship(
        back_populates="package", cascade="all, delete-orphan", lazy="selectin"
    )
    dependencies: Mapped[list[PackageDepEdge]] = relationship(
        back_populates="package", cascade="all, delete-orphan", lazy="selectin"
    )


class PackageVuln(TimestampMixin, Base):
    __tablename__ = "package_vulns"
    __table_args__ = (UniqueConstraint("monitored_package_id", "vuln_id", name="uq_package_vuln"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    monitored_package_id: Mapped[int] = mapped_column(
        ForeignKey("monitored_packages.id", ondelete="CASCADE"), nullable=False
    )
    vuln_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    """ID OSV/CVE/GHSA."""
    severity: Mapped[str | None] = mapped_column(String(20))
    adjusted_severity: Mapped[str | None] = mapped_column(String(20))
    kev: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    epss: Mapped[float | None] = mapped_column(Float)
    acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    package: Mapped[MonitoredPackage] = relationship(back_populates="vulns")
    aliases: Mapped[list[PackageVulnAlias]] = relationship(
        back_populates="vuln", cascade="all, delete-orphan", lazy="selectin"
    )


class PackageVulnAlias(Base):
    __tablename__ = "package_vuln_aliases"
    __table_args__ = (UniqueConstraint("package_vuln_id", "alias", name="uq_package_vuln_alias"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    package_vuln_id: Mapped[int] = mapped_column(
        ForeignKey("package_vulns.id", ondelete="CASCADE"), nullable=False
    )
    alias: Mapped[str] = mapped_column(String(50), nullable=False)

    vuln: Mapped[PackageVuln] = relationship(back_populates="aliases")


class PackageDepEdge(Base):
    """Edge graf dependensi: monitored_package TERGANTUNG PADA
    (depends_on, depends_on_ecosystem)."""

    __tablename__ = "package_dep_edges"
    __table_args__ = (
        UniqueConstraint(
            "monitored_package_id",
            "depends_on",
            "depends_on_ecosystem",
            name="uq_package_dep_edge",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    monitored_package_id: Mapped[int] = mapped_column(
        ForeignKey("monitored_packages.id", ondelete="CASCADE"), nullable=False
    )
    depends_on: Mapped[str] = mapped_column(String(300), nullable=False)
    depends_on_ecosystem: Mapped[str] = mapped_column(String(30), nullable=False)
    depends_on_version: Mapped[str | None] = mapped_column(String(100))

    package: Mapped[MonitoredPackage] = relationship(back_populates="dependencies")
