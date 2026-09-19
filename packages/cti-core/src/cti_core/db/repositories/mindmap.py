"""AsyncMindmapRepo -- cache generik `(feature_type, doc_id) -> mermaid
syntax`. Fase 7.3 (router `mindmap`, Bagian 4). Builder per feature_type
(nge-generate syntax dari data domain lain) ada di `cti_api.services.
mindmap`, BUKAN di sini -- repo ini murni persistensi cache."""

from __future__ import annotations

import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cti_core.db.models.mindmap import MindmapDoc


class AsyncMindmapRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_cached(self, feature_type: str, doc_id: str) -> MindmapDoc | None:
        result = await self.session.execute(
            select(MindmapDoc).where(
                MindmapDoc.feature_type == feature_type, MindmapDoc.doc_id == doc_id
            )
        )
        return result.scalar_one_or_none()

    async def save(self, feature_type: str, doc_id: str, title: str, syntax: str) -> MindmapDoc:
        existing = await self.get_cached(feature_type, doc_id)
        now = datetime.datetime.now(datetime.UTC).isoformat()
        if existing is not None:
            existing.title = title
            existing.mermaid_syntax = syntax
            existing.custom_syntax = None
            existing.generated_at = now
            existing.edited_at = None
            await self.session.flush()
            return existing
        row = MindmapDoc(
            feature_type=feature_type,
            doc_id=doc_id,
            title=title,
            mermaid_syntax=syntax,
            generated_at=now,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def save_custom_syntax(
        self, feature_type: str, doc_id: str, custom_syntax: str
    ) -> MindmapDoc | None:
        existing = await self.get_cached(feature_type, doc_id)
        if existing is None:
            return None
        existing.custom_syntax = custom_syntax
        existing.edited_at = datetime.datetime.now(datetime.UTC).isoformat()
        await self.session.flush()
        return existing


def get_display_syntax(doc: MindmapDoc) -> str:
    return doc.custom_syntax or doc.mermaid_syntax or ""
