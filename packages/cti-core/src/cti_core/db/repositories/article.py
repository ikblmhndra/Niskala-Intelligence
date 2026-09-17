"""ArticleRepo -- satu-satunya jalur tulis/baca tabel `articles`.

Aturan inti (plan §5.6, gantiin `$setOnInsert`-only upsert lama yang bikin
re-scrape gak pernah update artikel yang udah ada):
  - Field IDENTITAS (url, url_hash) cuma diisi sekali, waktu insert.
  - Field MESIN (title, source, confidence_score, dst) di-`$set` bebas tiap
    upsert -- scraper/enrichment boleh nimpa terus.
  - Field `overrides` (hasil edit analis lewat web) TIDAK PERNAH disentuh
    upsert ini. `to_dict()` yang gabungin overrides ke atas field mesin,
    overrides menang.
"""

from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from cti_core.db.models.article import Article
from cti_core.urlkit import url_hash as compute_url_hash

_RESERVED_OVERRIDE_KEYS = frozenset({"_meta"})


def _merge_overrides(article: Article) -> dict[str, Any]:
    base = {c.name: getattr(article, c.name) for c in Article.__table__.columns}
    overrides = {k: v for k, v in article.overrides.items() if k not in _RESERVED_OVERRIDE_KEYS}
    return {**base, **overrides}


def _apply_machine_fields(article: Article, machine_fields: dict[str, Any]) -> None:
    valid_columns = Article.__table__.columns.keys()
    for k, v in machine_fields.items():
        if k not in valid_columns:
            raise ValueError(f"'{k}' bukan kolom Article -- typo, atau harusnya masuk overrides?")
        if k in ("id", "url", "url_hash", "overrides", "created_at"):
            raise ValueError(f"'{k}' itu field identitas/override, upsert() gak boleh nimpa ini")
        setattr(article, k, v)


class ArticleRepo:
    """Sync -- dipakai scraper/enrichment (Celery task), CLI."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert(self, *, url: str, title: str, source: str, **machine_fields: Any) -> Article:
        h = compute_url_hash(url)
        existing = self.session.execute(
            select(Article).where(Article.url_hash == h)
        ).scalar_one_or_none()
        now = datetime.datetime.now(datetime.UTC)

        if existing is None:
            article = Article(
                url=url,  # URL ASLI disimpan, bukan hasil canonicalize_url() -- url_hash yang
                # jadi kunci dedup; url tetap perlu bentuk aslinya buat ditampilkan/dibuka user
                url_hash=h,
                title=title,
                source=source,
                first_seen_at=now,
                last_seen_at=now,
                seen_count=1,
            )
            _apply_machine_fields(article, machine_fields)
            self.session.add(article)
            self.session.flush()
            return article

        existing.title = title
        existing.source = source
        existing.last_seen_at = now
        existing.seen_count += 1
        _apply_machine_fields(existing, machine_fields)
        self.session.flush()
        return existing

    def get_by_url_hash(self, url_hash_value: str) -> Article | None:
        return self.session.execute(
            select(Article).where(Article.url_hash == url_hash_value)
        ).scalar_one_or_none()

    def get_by_url(self, url: str) -> Article | None:
        return self.get_by_url_hash(compute_url_hash(url))

    def set_overrides(self, article: Article, **overrides: Any) -> Article:
        """Satu-satunya jalur analis nulis koreksi manual -- lihat plan §5.6.
        Dipanggil dari layer web (Fase 7), bukan dari scraper/enrichment."""
        article.overrides = {**article.overrides, **overrides}
        self.session.flush()
        return article

    def to_dict(self, article: Article) -> dict[str, Any]:
        """Field mesin + overrides tergabung, overrides menang. Ini yang
        dibaca API/dashboard -- JANGAN baca kolom Article langsung kalau
        butuh nilai yang analis udah koreksi."""
        return _merge_overrides(article)


class AsyncArticleRepo:
    """Async -- dipakai FastAPI (Fase 7). Logic sama persis ArticleRepo,
    beda cuma `await` -- lihat plan §5.2 soal rasio duplikasi ini."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(self, *, url: str, title: str, source: str, **machine_fields: Any) -> Article:
        h = compute_url_hash(url)
        result = await self.session.execute(select(Article).where(Article.url_hash == h))
        existing = result.scalar_one_or_none()
        now = datetime.datetime.now(datetime.UTC)

        if existing is None:
            article = Article(
                url=url,
                url_hash=h,
                title=title,
                source=source,
                first_seen_at=now,
                last_seen_at=now,
                seen_count=1,
            )
            _apply_machine_fields(article, machine_fields)
            self.session.add(article)
            await self.session.flush()
            return article

        existing.title = title
        existing.source = source
        existing.last_seen_at = now
        existing.seen_count += 1
        _apply_machine_fields(existing, machine_fields)
        await self.session.flush()
        return existing

    async def get_by_url_hash(self, url_hash_value: str) -> Article | None:
        result = await self.session.execute(
            select(Article).where(Article.url_hash == url_hash_value)
        )
        return result.scalar_one_or_none()

    async def get_by_url(self, url: str) -> Article | None:
        return await self.get_by_url_hash(compute_url_hash(url))

    async def set_overrides(self, article: Article, **overrides: Any) -> Article:
        article.overrides = {**article.overrides, **overrides}
        await self.session.flush()
        return article

    def to_dict(self, article: Article) -> dict[str, Any]:
        return _merge_overrides(article)
