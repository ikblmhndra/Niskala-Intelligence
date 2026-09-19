"""Adaptasi dari body `dict`/`Body(...)` TANPA validasi di
`ScraperNewsWeb/app/routers/newsletter.py` -- Pydantic model eksplisit
di sini, port `article id` dari ObjectId string ke `int`. Konsisten sama
router lain (RFI/PIR dst) yang juga naikin dict lepas jadi model
tervalidasi, bukan keputusan baru khusus newsletter."""

from __future__ import annotations

from pydantic import BaseModel


class NewsletterSectionsBody(BaseModel):
    highlight: int
    apac: list[int] = []
    global_news: list[int] = []
    indonesia: list[int] = []
    custom_css: str = ""
    custom_intro: str = ""
    custom_footer: str = ""
    notes: dict[str, str] = {}
    """Key = `str(article.id)`, sama pola kayak kode lama (dulu
    `str(ObjectId)`)."""
    include_clusters: bool = False
    cluster_days: int = 7


class NewsletterListItem(BaseModel):
    id: int
    week: int
    year: int
    generated_at: str
    created_by: str
    created_at: str
    sections: dict[str, object]


class NewsletterListResponse(BaseModel):
    newsletters: list[NewsletterListItem]
    total: int
    page: int
    page_size: int
