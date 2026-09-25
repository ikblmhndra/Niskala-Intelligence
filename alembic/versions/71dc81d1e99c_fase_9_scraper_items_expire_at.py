"""fase 9: scraper_items.expire_at

Revision ID: 71dc81d1e99c
Revises: 6e5de9ec8b9b
Create Date: 2026-09-25 20:19:04.150524

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "71dc81d1e99c"
down_revision: str | None = "6e5de9ec8b9b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # scraper_items kosong (gak ada kode yang nulis ke sini sebelum Fase 9),
    # tapi tetep pakai pola server_default sementara -- konsisten sama
    # migration lain yang nambah kolom NOT NULL, jaga-jaga ada baris manual.
    op.add_column(
        "scraper_items",
        sa.Column(
            "expire_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
    )
    op.alter_column("scraper_items", "expire_at", server_default=None)
    op.create_index(op.f("ix_scraper_items_expire_at"), "scraper_items", ["expire_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_scraper_items_expire_at"), table_name="scraper_items")
    op.drop_column("scraper_items", "expire_at")
