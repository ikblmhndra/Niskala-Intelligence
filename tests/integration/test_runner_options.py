"""`Runner` + opsi per-scraper (`ScraperMeta.options`): pilihan admin di `scraper_config`
menentukan KREDENSIAL yang dipasang dan `ctx.options` yang dilihat `fetch()`.

Yang dibuktikan di sini justru sambungan antar lapisan (DB -> Runner -> header HTTP), bukan
logika pilihannya sendiri (itu di `tests/unit/test_scraper_options.py`). Scraper palsu
`__abstract__ = True` supaya tidak nyelip ke registry global.
"""

from __future__ import annotations

from collections.abc import Iterator

import httpx
import pytest
from cti_core.config import get_settings
from cti_core.db.models.scraper import ScraperConfig
from cti_scraper.base import (
    BaseScraper,
    OptionChoice,
    ScrapeContext,
    ScraperMeta,
    ScraperOption,
)
from cti_scraper.items import Item
from cti_scraper.options import OptionError
from cti_scraper.runner import Runner
from sqlalchemy.orm import Session

SCRAPER_ID = "test-options"

SOURCE = ScraperOption(
    key="source",
    label="Sumber",
    choices=(
        OptionChoice("io", "twitterapi.io", credential="twitter"),
        OptionChoice("official", "X resmi", credential="x"),
    ),
    default="io",
)


class Probe:
    """Apa yang dilihat scraper + request HTTP yang keluar."""

    def __init__(self) -> None:
        self.ctx_options: dict[str, str] | None = None
        self.requests: list[httpx.Request] = []

    def transport(self) -> httpx.MockTransport:
        def handler(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            return httpx.Response(200, json={})

        return httpx.MockTransport(handler)


def make_scraper(probe: Probe) -> type[BaseScraper]:
    class _Scraper(BaseScraper):
        __abstract__ = True
        meta = ScraperMeta(
            id=SCRAPER_ID,
            source="Test",
            schedule="0 * * * *",
            credential="twitter",
            options=(SOURCE,),
        )

        def fetch(self, ctx: ScrapeContext) -> Iterator[Item]:
            probe.ctx_options = dict(ctx.options)
            ctx.http.get("https://svc.example/search")
            return iter(())

    return _Scraper


@pytest.fixture
def session(_migrated_schema: None) -> Iterator[Session]:
    from cti_core.db.engine import get_sync_engine

    connection = get_sync_engine().connect()
    connection.begin()
    s = Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
    try:
        yield s
    finally:
        s.close()
        connection.rollback()
        connection.close()


@pytest.fixture(autouse=True)
def _both_secrets_set(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """`get_settings()` juga baca `.env` di cwd -- set eksplisit lewat env (menang atas dotenv)
    biar hasil tes tidak bergantung ke key yang kebetulan ada di `.env` dev."""
    monkeypatch.setenv("TWITTER__API_KEY", "io-secret")
    monkeypatch.setenv("X__BEARER_TOKEN", "x-secret")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def choose(session: Session, **options: str) -> None:
    session.add(ScraperConfig(scraper_id=SCRAPER_ID, enabled=True, options=options))
    session.flush()


def run(session: Session, probe: Probe, **kw: object):
    return Runner(
        make_scraper(probe),
        session=session,
        transport=probe.transport(),
        cold_start_max_items=0,
        **kw,  # type: ignore[arg-type]
    ).execute()


def sent_headers(probe: Probe) -> httpx.Headers:
    [request] = probe.requests
    return request.headers


def test_without_any_config_the_default_choice_and_its_credential_apply(session: Session) -> None:
    probe = Probe()

    result = run(session, probe)

    assert result.status == "empty"
    assert probe.ctx_options == {"source": "io"}
    assert sent_headers(probe)["x-api-key"] == "io-secret"
    assert "authorization" not in sent_headers(probe)


def test_the_admins_choice_in_the_db_switches_the_credential_and_ctx_options(
    session: Session,
) -> None:
    choose(session, source="official")
    probe = Probe()

    result = run(session, probe)

    assert result.status == "empty"
    assert probe.ctx_options == {"source": "official"}
    assert sent_headers(probe)["authorization"] == "Bearer x-secret"
    assert "x-api-key" not in sent_headers(probe)  # kunci sumber LAIN tidak bocor ke sumber ini


def test_an_explicit_override_beats_the_admins_choice_without_touching_the_db(
    session: Session,
) -> None:
    choose(session, source="io")
    probe = Probe()

    run(session, probe, options={"source": "official"})

    assert probe.ctx_options == {"source": "official"}
    assert sent_headers(probe)["authorization"] == "Bearer x-secret"
    session.expire_all()
    assert session.get(ScraperConfig, SCRAPER_ID).options == {"source": "io"}  # type: ignore[union-attr]


def test_a_stale_stored_choice_falls_back_to_the_default_and_the_run_still_works(
    session: Session,
) -> None:
    """Pilihan yang sudah dihapus dari kode tidak boleh mematikan scraper tiap jadwal."""
    choose(session, source="sudah-dihapus", opsi_hantu="x")
    probe = Probe()

    result = run(session, probe)

    assert result.status == "empty"
    assert probe.ctx_options == {"source": "io"}
    assert sent_headers(probe)["x-api-key"] == "io-secret"


def test_choosing_official_without_its_secret_fails_the_run_instead_of_using_the_other_key(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tidak ada fallback diam-diam ke twitterapi.io: admin memilih X resmi -> kalau bearer-nya
    kosong, run GAGAL jelas (stage config), bukan diam-diam jalan di sumber yang lain."""
    monkeypatch.setenv("X__BEARER_TOKEN", "")
    get_settings.cache_clear()
    choose(session, source="official")
    probe = Probe()

    result = run(session, probe)

    assert result.status == "fetch_error"
    assert result.errors[0]["stage"] == "config" and "'x'" in result.errors[0]["message"]
    assert probe.requests == []  # tidak ada request keluar tanpa auth


def test_a_bad_explicit_override_is_rejected_before_the_run_starts(session: Session) -> None:
    probe = Probe()

    with pytest.raises(OptionError, match="tidak boleh 'nope'"):
        Runner(make_scraper(probe), session=session, options={"source": "nope"})

    assert probe.requests == []
