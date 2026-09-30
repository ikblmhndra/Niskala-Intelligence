"""State kecil buat laporan periodik Fase 10.E -- gantiin file/koleksi lokal
skrip lama yang hilang tiap container di-restart:

  - `cve_mentions`  <- koleksi Mongo `cve_mentions` (`dbMongo.update_cve_mention`)
    DAN `offset/existCve.json` (`TwitterScrap/trendingCve.py`). Dua penghitung
    yang bentuknya sama; dibedakan kolom `scope`.
  - `job_state`     <- `logbook_meta.last_report_date` dan `offset/lastTweetId.txt`:
    satu nilai kecil per kunci.
"""

from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import BigInteger, Date, DateTime, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from cti_core.db.base import Base

SCOPE_NEWS = "news"
SCOPE_TWEET = "tweet"


class CveMention(Base):
    """Berapa kali sebuah CVE disebut sejak laporan terakhir yang memasukkannya.

    `scope="news"`: artikel yang lolos enrichment (judul + isi) -> laporan Top CVE
    mingguan. `scope="tweet"`: tweet hasil pencarian `CVE-<tahun>-` -> laporan
    "Top CVE 6 jam". Counter di-RESET (bukan dihapus) begitu CVE-nya dilaporkan,
    sama seperti `reset_cve_counter` lama, supaya laporan berikutnya cuma menghitung
    mention BARU.

    Beda dari koleksi lama: TIDAK dipecah per bulan (`year_month`). Skema lama
    bikin mention di 3 hari terakhir bulan lalu hilang dari laporan minggu pertama
    bulan ini; sekarang jendela 7 hari dihitung dari `last_seen_on` saja."""

    __tablename__ = "cve_mentions"
    __table_args__ = (
        UniqueConstraint("scope", "cve_id", name="uq_cve_mentions_scope_cve"),
        Index("ix_cve_mentions_scope_last_seen", "scope", "last_seen_on"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String(20), nullable=False)
    cve_id: Mapped[str] = mapped_column(String(30), nullable=False)
    """Selalu UPPERCASE ("CVE-2026-1234")."""
    counter: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_seen_on: Mapped[datetime.date] = mapped_column(Date, nullable=False)


class JobState(Base):
    """Nilai kecil per job periodik (kunci bebas, mis. "logbook.last_report_date")."""

    __tablename__ = "job_state"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[Any] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
