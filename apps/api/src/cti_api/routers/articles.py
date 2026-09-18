"""Port dari `ScraperNewsWeb/app/routers/articles.py` -- cuma permukaan
BACA (list/filter/detail) buat sekarang. **Belum diport** (nyusul, masing-
masing butuh porting terpisah dulu): `/api/dashboard` (agregasi berat,
butuh normalisasi negara yang SEKARANG udah kejadian di enrichment --
lihat catatan `cti_enrich.countries`, bukan lagi query-time kayak
`normalize_country()` lama), `/api/articles/dedup-groups` (butuh
scikit-learn, belum ada di dependency `cti-api`), `/api/articles/{id}/confidence`
+ `/confidence/recompute` (butuh `source_reliability` router/data ke-port
duluan), `/api/articles/backfill-iocs` (hack migrasi era Mongo, kemungkinan
besar OBSOLETE di skema baru -- `persist.py` Fase 5 udah nulis IOC lewat
jalur normal, bukan backfill URL-match belakangan). `/api/country-groups`
juga SENGAJA di-skip -- itu peta nama->varian buat data negara yang dulu
FREE-TEXT; skema baru (`ArticleCountry.country_code`) udah ISO alpha-2 dari
enrichment, gak ada lagi varian nama yang perlu di-grup di layer API."""

from __future__ import annotations

import datetime

from cti_core.db.models.article import Article
from cti_core.db.repositories.article import AsyncArticleRepo
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from cti_api.deps import get_db, require_auth
from cti_api.schemas.article import TTP, ArticleListResponse, ArticleOut, FilterOptions

router = APIRouter(prefix="/api", tags=["articles"])
"""`list_articles`/`list_filters` SENGAJA gak pakai `require_auth` --
port apa adanya dari legacy (`routers/articles.py` asli juga gak ngasih
dependency itu ke keduanya, cuma endpoint detail `{article_id}` yang
di-gate). Asimetri ini ada di kode lama, bukan keputusan baru di sini."""


def _serialize(article: Article, machine_fields: dict[str, object]) -> ArticleOut:
    posted_on = machine_fields.get("posted_on")
    year, month, week = 0, "", ""
    if isinstance(posted_on, datetime.date):
        iso_year, iso_week, _ = posted_on.isocalendar()
        year = posted_on.year
        month = f"{posted_on.year:04d}-{posted_on.month:02d}"
        week = f"{iso_year:04d}-W{iso_week:02d}"

    return ArticleOut(
        id=article.id,
        year=year,
        month=month,
        week=week,
        title=str(machine_fields.get("title", "")),
        url=str(machine_fields.get("url", "")),
        posted_on=posted_on.isoformat() if isinstance(posted_on, datetime.date) else "",
        source=str(machine_fields.get("source", "")),
        impacted_industries=[i.industry for i in article.industries],
        mentioned_countries=[c.country_code for c in article.countries if c.role == "mentioned"],
        victim_countries=[c.country_code for c in article.countries if c.role == "victim"],
        actor_countries=[c.country_code for c in article.countries if c.role == "actor"],
        threat_actors=[t.threat_actor for t in article.threat_actors],
        ttps=[TTP(id=t.ttp_id, name=t.ttp_name) for t in article.ttps],
        news_type=str(machine_fields.get("news_type") or ""),
        confidence_score=machine_fields.get("confidence_score"),  # type: ignore[arg-type]
        iocs={},
    )


@router.get("/articles", response_model=ArticleListResponse)
async def list_articles(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    posted_on_start: datetime.date | None = None,
    posted_on_end: datetime.date | None = None,
    industry: list[str] | None = Query(None),
    country: list[str] | None = Query(None),
    source: list[str] | None = Query(None),
    news_type: list[str] | None = Query(None),
    threat_actor: list[str] | None = Query(None),
    search: str | None = None,
    victim_country: list[str] | None = Query(None),
    actor_country: list[str] | None = Query(None),
    title_keyword: list[str] | None = Query(None),
    session: AsyncSession = Depends(get_db),
) -> ArticleListResponse:
    repo = AsyncArticleRepo(session)
    articles, total = await repo.list_filtered(
        page=page,
        page_size=page_size,
        posted_on_start=posted_on_start,
        posted_on_end=posted_on_end,
        industries=industry,
        countries=country,
        victim_countries=victim_country,
        actor_countries=actor_country,
        sources=source,
        news_types=news_type,
        threat_actors=threat_actor,
        search=search,
        title_keywords=title_keyword,
    )
    parsed = [_serialize(a, repo.to_dict(a)) for a in articles]
    return ArticleListResponse(articles=parsed, total=total, page=page, page_size=page_size)


@router.get("/filters", response_model=FilterOptions)
async def list_filters(session: AsyncSession = Depends(get_db)) -> FilterOptions:
    options = await AsyncArticleRepo(session).get_filter_options()
    return FilterOptions(**options)


@router.get(
    "/articles/{article_id}",
    response_model=ArticleOut,
    dependencies=[Depends(require_auth)],
)
async def get_article_by_id(article_id: int, session: AsyncSession = Depends(get_db)) -> ArticleOut:
    repo = AsyncArticleRepo(session)
    article = await repo.get_by_id(article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return _serialize(article, repo.to_dict(article))
