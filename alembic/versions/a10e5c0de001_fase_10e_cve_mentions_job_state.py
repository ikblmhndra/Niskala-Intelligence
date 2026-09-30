"""fase 10.E: tabel cve_mentions dan job_state

Penghitung mention CVE (laporan Top CVE mingguan + Top CVE tweet 6 jam) dan state
kecil per job periodik (tanggal logbook terakhir, kursor tweet).

Revision ID: a10e5c0de001
Revises: 71dc81d1e99c
Create Date: 2026-09-26 17:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a10e5c0de001"
down_revision: str | None = "71dc81d1e99c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cve_mentions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("scope", sa.String(length=20), nullable=False),
        sa.Column("cve_id", sa.String(length=30), nullable=False),
        sa.Column("counter", sa.Integer(), nullable=False),
        sa.Column("last_seen_on", sa.Date(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cve_mentions")),
        sa.UniqueConstraint("scope", "cve_id", name="uq_cve_mentions_scope_cve"),
    )
    op.create_index(
        "ix_cve_mentions_scope_last_seen", "cve_mentions", ["scope", "last_seen_on"], unique=False
    )
    op.create_table(
        "job_state",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_job_state")),
    )


def downgrade() -> None:
    op.drop_table("job_state")
    op.drop_index("ix_cve_mentions_scope_last_seen", table_name="cve_mentions")
    op.drop_table("cve_mentions")
