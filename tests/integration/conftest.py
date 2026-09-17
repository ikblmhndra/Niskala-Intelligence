"""Fixture Postgres buat test integrasi -- testcontainers nyalain container
EFEMERAL sendiri (beda dari container docker-compose yang dipakai manual
waktu dev), supaya CI bisa jalanin ini tanpa setup tambahan apa pun.

Scope "session": satu container buat semua test integrasi dalam satu run
pytest -- nyalain Postgres ~2 detik, jangan diulang per test.
"""

from __future__ import annotations

import os
import pathlib
from collections.abc import AsyncIterator, Iterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from testcontainers.community.postgres import PostgresContainer


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    with PostgresContainer("postgres:16-alpine") as pg:
        sync_url = pg.get_connection_url().replace(
            "postgresql+psycopg2://", "postgresql+psycopg://"
        )
        yield sync_url


@pytest.fixture(scope="package")
def _configured_settings(postgres_url: str) -> Iterator[None]:
    """Arahin cti_core.config ke Postgres efemeral.

    Scope "package" (BUKAN "session") disengaja: fixture ini ngubah
    `os.environ` GLOBAL (AUTH__JWT_SECRET dkk). Kalau di-scope "session",
    teardown-nya baru jalan di akhir SELURUH pytest run -- kalau
    `tests/integration/` kebetulan jalan sebelum `tests/unit/` (urutan
    alfabetis: "integration" < "unit"), env var bocor ke test lain dan
    bikin `test_missing_required_secret_fails_loud` di test_config.py
    gagal karena AUTH__JWT_SECRET udah keisi "test-secret" dari sini.
    Ketauan dari full-suite run, bukan dugaan -- lihat commit message."""
    async_url = postgres_url.replace("postgresql+psycopg://", "postgresql+asyncpg://")
    env = {
        "DATABASE__URL": async_url,
        "DATABASE__SYNC_URL": postgres_url,
        "AUTH__JWT_SECRET": "test-secret",
        "AUTH__SESSION_SECRET_KEY": "test-session",
    }
    old = {k: os.environ.get(k) for k in env}
    os.environ.update(env)

    from cti_core.config import get_settings
    from cti_core.db.engine import reset_engines

    get_settings.cache_clear()
    reset_engines()

    yield

    for k, v in old.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    get_settings.cache_clear()
    reset_engines()


@pytest.fixture(scope="package")
def _migrated_schema(_configured_settings: None) -> Iterator[None]:
    """`alembic upgrade head` beneran, sama persis yang dijalanin di
    deployment (bukan `Base.metadata.create_all()` -- itu gak nguji migrasi
    yang sesungguhnya dipakai buat naikin skema di produksi).

    Scope "package" ngikutin _configured_settings -- pytest nolak fixture
    "session" yang depend ke fixture "package" (lebih sempit)."""
    from alembic.config import Config

    from alembic import command

    root = _find_repo_root()
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    command.upgrade(cfg, "head")

    yield

    command.downgrade(cfg, "base")


def _find_repo_root() -> pathlib.Path:
    p = pathlib.Path(__file__).resolve()
    while not (p / "alembic.ini").exists():
        if p.parent == p:
            raise RuntimeError("alembic.ini gak ketemu di parent mana pun")
        p = p.parent
    return p


@pytest.fixture
def db_session(_migrated_schema: None) -> Iterator[Session]:
    """Sesi sync per-test, di-rollback di akhir -- satu test gak
    kecemar hasil test lain."""
    from cti_core.db.engine import get_sync_engine

    engine = get_sync_engine()
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
async def async_db_session(_migrated_schema: None) -> AsyncIterator[AsyncSession]:
    from cti_core.db.engine import get_async_engine

    engine = get_async_engine()
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection)
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


@pytest.fixture(autouse=True)
def _skip_if_docker_unavailable() -> None:
    """Testcontainers butuh Docker daemon. Kalau gak ada, skip jelas --
    bukan error yang bikin bingung."""
    import shutil
    import subprocess

    if not shutil.which("docker"):
        pytest.skip("butuh Docker buat test integrasi")
    try:
        subprocess.run(["docker", "info"], capture_output=True, timeout=5, check=True)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        pytest.skip("Docker daemon gak jalan")
