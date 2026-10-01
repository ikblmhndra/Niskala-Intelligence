"""qa 2026-10-01: normalisasi TTP artikel ke katalog ATT&CK

- `article_ttps.extracted_id`/`extracted_name`: pasangan ID/nama ASLI dari LLM. `ttp_id`/`ttp_name`
  sekarang hasil normalisasi ke katalog (`cti_core.attack_ttp`). Nullable: baris lama tetap valid,
  diisi oleh `tools/ops/remap_article_ttps.py`.
- `attack_technique_aliases`: technique REVOKED dari bundel STIX (nama/ID lama -> pengganti), diisi
  sync ATT&CK berikutnya.

Revision ID: c3a7e9d1f2b4
Revises: a10e5c0de002
Create Date: 2026-10-01 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3a7e9d1f2b4"
down_revision: str | None = "a10e5c0de002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("article_ttps", sa.Column("extracted_id", sa.String(length=50), nullable=True))
    op.add_column("article_ttps", sa.Column("extracted_name", sa.String(length=300), nullable=True))
    op.create_table(
        "attack_technique_aliases",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("stix_id", sa.String(length=100), nullable=False),
        sa.Column("attack_id", sa.String(length=20), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("revoked_by_stix_id", sa.String(length=100), nullable=True),
        sa.Column("domains", postgresql.ARRAY(sa.String(length=20)), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attack_technique_aliases")),
    )
    op.create_index(
        op.f("ix_attack_technique_aliases_stix_id"),
        "attack_technique_aliases",
        ["stix_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_attack_technique_aliases_attack_id"),
        "attack_technique_aliases",
        ["attack_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_attack_technique_aliases_attack_id"), table_name="attack_technique_aliases"
    )
    op.drop_index(
        op.f("ix_attack_technique_aliases_stix_id"), table_name="attack_technique_aliases"
    )
    op.drop_table("attack_technique_aliases")
    op.drop_column("article_ttps", "extracted_name")
    op.drop_column("article_ttps", "extracted_id")
