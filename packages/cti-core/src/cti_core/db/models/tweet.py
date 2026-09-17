"""X/Twitter intel -- gantiin `news_db.tweets` + `monitored_accounts`.

`monitored_accounts` itu salah satu dari TIGA pola "web kurasi, scraper
patuh" yang udah kebukti bagus di sistem lama (dua lainnya: ioc_allowlist,
techstack) -- lihat plan §8.3. Framework baru men-generalisasi pola ini,
bukan cuma niruin.

Field hasil regex-scan (`scan_results`) sengaja JSONB, BUKAN tabel anak --
beda dari Article yang dinormalisasi penuh. Alasannya: ini hasil pencocokan
regex sekali pakai dari `monitorX.py:33-90` buat satu tweet, bukan data
relasional yang perlu di-query lintas baris (gak ada use case "semua tweet
yang nyebut Indonesia sebagai victim" yang butuh index terpisah, beda sama
Article.countries yang emang butuh itu).
"""

from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from cti_core.db.base import Base, TimestampMixin


class MonitoredAccount(TimestampMixin, Base):
    __tablename__ = "monitored_accounts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Tweet(TimestampMixin, Base):
    __tablename__ = "tweets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tweet_id: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    author_username: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    author_name: Mapped[str | None] = mapped_column(String(200))
    author_avatar: Mapped[str | None] = mapped_column(Text)
    author_followers: Mapped[int | None] = mapped_column(Integer)

    posted_on: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    lang: Mapped[str | None] = mapped_column(String(10))
    media_urls: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    fetched_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    scan_results: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    """apac_indicator, mentioned_group, mentioned_apac_country,
    mentioned_apac_people, cve_list, zero_day_list, databreach_list,
    ot_status, report_status -- lihat monitorX.py:33-90."""

    confidence_score: Mapped[int | None] = mapped_column(SmallInteger)
    confirmed_incident: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
