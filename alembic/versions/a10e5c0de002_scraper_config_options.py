"""fase 10.E: scraper_config.options (pilihan per-scraper dari control plane)

Kolom JSONB `{key: value}` buat `ScraperMeta.options` -- pertama dipakai buat memilih sumber
data Twitter per-scraper (twitterapi.io vs API resmi X). Nullable: baris yang sudah ada
tetap valid dan artinya "semua opsi pakai default kode".

Revision ID: a10e5c0de002
Revises: a10e5c0de001
Create Date: 2026-09-26 21:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a10e5c0de002"
down_revision: str | None = "a10e5c0de001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "scraper_config",
        sa.Column("options", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("scraper_config", "options")
