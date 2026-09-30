"""Skema hasil `alembic upgrade head` harus sama dengan model SQLAlchemy.

Latar: migrasi Fase 10.E ditulis tangan (autogenerate butuh DB hidup). Tanpa
test ini, kolom/constraint yang lupa masuk migrasi baru ketahuan di produksi --
model bilang ada, tabelnya enggak. `compare_metadata` = mesin yang sama dengan
`alembic revision --autogenerate`; diff kosong = migrasi lengkap.

Diukur 2026-09-26: SELURUH skema (bukan cuma tabel baru) sudah nol drift, jadi
guard ini berlaku untuk semua tabel dan migrasi berikutnya.
"""

from __future__ import annotations

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from cti_core.db.base import Base
from cti_core.db.engine import get_sync_engine


@pytest.mark.usefixtures("_migrated_schema")
def test_migrations_produce_exactly_the_schema_the_models_declare() -> None:
    import cti_core.db.models  # noqa: F401  -- daftarkan semua model ke metadata

    with get_sync_engine().connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"compare_type": True})
        drift = compare_metadata(ctx, Base.metadata)

    assert drift == []
