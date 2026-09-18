"""Response shape ransomware victim -- gak ada Pydantic model terpisah di
legacy (router lama balikin dict Mongo mentah), didefinisikan eksplisit
di sini biar konsisten sama router lain."""

from __future__ import annotations

from pydantic import BaseModel


class RansomwareVictimOut(BaseModel):
    id: int
    group_name: str
    victim: str
    domain: str | None = None
    description: str | None = None
    country_code: str | None = None
    industry: str | None = None
    published: str | None = None
    discovered: str | None = None
    post_url: str = "Unknown"
    ransom: str | None = None
    data_size: str | None = None
    screenshot: str | None = None
