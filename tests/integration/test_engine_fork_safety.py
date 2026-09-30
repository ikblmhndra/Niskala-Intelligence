"""`cti_core.db.engine.discard_inherited_connections` -- koneksi DB gak boleh
dibagi antar proses hasil fork.

Celery prefork nge-fork anak dari induk yang SUDAH punya pool berisi koneksi
(`build_beat_schedule()` baca DB pas import). Dua anak yang make socket yang
sama ngerusak protokol Postgres: `server closed the connection unexpectedly`
lalu `PendingRollbackError` (e2e staging Fase 10: scraper nyangkut `running`).
"""

from __future__ import annotations

import os
import sys

import pytest
from sqlalchemy import text

pytestmark = [
    pytest.mark.skipif(sys.platform == "win32", reason="butuh os.fork"),
    pytest.mark.filterwarnings("ignore:This process .* is multi-threaded:DeprecationWarning"),
]


def test_discard_drops_the_inherited_pool_without_closing_the_parents_connection(
    _migrated_schema: None,
) -> None:
    from cti_core.db.engine import discard_inherited_connections, get_sync_engine

    engine = get_sync_engine()
    with engine.connect() as c:
        c.execute(text("select 1"))
    old_pool = engine.pool
    raw = engine.raw_connection()
    dbapi = raw.dbapi_connection
    raw.close()  # balik ke pool, MASIH terbuka
    assert engine.pool.checkedin() >= 1

    discard_inherited_connections()

    assert engine.pool is not old_pool  # pool baru
    assert engine.pool.checkedin() == 0  # ... dan kosong: gak ada koneksi warisan
    assert dbapi is not None and not dbapi.closed  # milik INDUK, harus tetap hidup
    with engine.connect() as c:  # engine tetap bisa dipakai ulang
        assert c.execute(text("select 1")).scalar() == 1


def test_forked_children_hammering_the_same_engine_do_not_corrupt_each_other(
    _migrated_schema: None,
) -> None:
    """Skenario asli: induk punya pool hangat, tiga anak (concurrency worker)
    sama-sama query. Dengan `discard_inherited_connections()` di tiap anak
    (`worker_process_init`), semuanya bersih dan koneksi induk tetap sehat."""
    from cti_core.db.engine import discard_inherited_connections, get_sync_engine

    engine = get_sync_engine()
    with engine.connect() as c:
        c.execute(text("select 1"))  # pool induk hangat -> bakal diwarisi

    pids = []
    for _ in range(3):
        pid = os.fork()
        if pid == 0:  # anak
            code = 0
            try:
                discard_inherited_connections()
                for _ in range(150):
                    with engine.connect() as c:
                        assert c.execute(text("select 1")).scalar() == 1
            except BaseException:
                code = 1
            os._exit(code)
        pids.append(pid)

    codes = [os.waitpid(pid, 0)[1] for pid in pids]

    assert codes == [0, 0, 0]
    with engine.connect() as c:  # koneksi induk gak rusak gara-gara anak-anaknya
        assert c.execute(text("select 1")).scalar() == 1
