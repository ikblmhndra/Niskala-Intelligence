"""Newsletter mingguan (kurasi analis + LLM summarization) -- gantiin
`news_db.newsletters` + `newsletter_paywall_hints`. Fase 7.3 (router
`newsletter`, Bagian 4).

`sections` (JSONB, bukan tabel anak) -- snapshot artikel yang UDAH
diringkas/di-enrich (title/url/source/key_points/summary/iocs/dst) BUKAN
data relasional yang perlu di-query per-field, murni presentasi arsip
histori ("kartu apa yang ditampilin newsletter minggu X") -- sama alasan
kayak `TAProfile.profile`. `html` juga disimpen utuh (arsip lengkap,
`GET /{id}/html`/`resend` baca langsung dari sini).

**`include_clusters` (fitur campaign clustering) SENGAJA belum diport**
-- itu butuh `cluster_service.py` (784 baris, TF-IDF + Jaccard similarity
buat ngelompokin artikel jadi "campaign"), fitur BERDIRI SENDIRI yang
gak ada di daftar 27 router manapun (dipakai OPSIONAL sama `newsletter`
DAN `mindmap`, tapi bukan salah satu dari keduanya). `campaign_clusters`
di context newsletter SELALU list kosong buat sekarang -- template
Jinja udah nge-guard `{% if campaign_clusters %}`, jadi render tetep
valid, cuma seksi itu gak pernah muncul. Port beneran nyusul kalau
`cluster_service.py` dikerjain (kemungkinan Fase 7.4, di luar scope
per-router Fase 7.3)."""

from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from cti_core.db.base import Base


class Newsletter(Base):
    __tablename__ = "newsletters"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    week: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    generated_at: Mapped[str] = mapped_column(String(40), nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    html: Mapped[str] = mapped_column(Text, nullable=False)
    sections: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    """{highlight, apac, global_news, indonesia} -- masing-masing snapshot
    artikel yang di-strip (`_strip_article` lama), lihat docstring modul."""


class NewsletterPaywallHint(Base):
    """Sumber yang kedetek paywall pas `fetch_article_body()` -- dipakai
    UI buat kasih hint "kemungkinan paywall" di daftar sumber, BUKAN
    dipakai buat skip fetch (fetch tetap dicoba tiap kali, hint cuma
    informational). Port apa adanya."""

    __tablename__ = "newsletter_paywall_hints"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(200), nullable=False, unique=True, index=True)
    paywall_likely: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_seen: Mapped[str] = mapped_column(String(40), nullable=False)
