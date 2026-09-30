"""Control plane: pilihan per-scraper (`ScraperMeta.options`) lewat `GET /api/scraper/{id}` dan
`PUT /api/scraper/{id}/config` -- validasi, hak akses, dan efeknya ke nilai efektif."""

from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar

import pytest
from cti_core.db.models.scraper import ScraperConfig
from cti_scraper.registry import discover
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio

TWEETS = "tweet_alerts_30m"
PLAIN = next(sid for sid, cls in sorted(discover().items()) if not cls.meta.options)


async def detail(client: AsyncClient, headers: dict[str, str], scraper_id: str = TWEETS) -> dict:
    resp = await client.get(f"/api/scraper/{scraper_id}", headers=headers)
    assert resp.status_code == 200
    return resp.json()


async def put_options(
    client: AsyncClient, headers: dict[str, str], options: object, scraper_id: str = TWEETS
):
    return await client.put(
        f"/api/scraper/{scraper_id}/config", headers=headers, json={"options": options}
    )


async def test_detail_lists_the_declared_option_with_its_effective_default(
    api_client: AsyncClient, auth_header: Callable[..., dict[str, str]]
) -> None:
    body = await detail(api_client, auth_header(role="admin"))

    [option] = body["options"]
    assert option["key"] == "provider"
    assert (option["default"], option["value"]) == ("twitterapi_io", "twitterapi_io")
    assert [c["value"] for c in option["choices"]] == ["twitterapi_io", "x_official"]
    assert "pay-per-use" in option["description"]
    assert body["config"]["options"] is None


async def test_a_scraper_without_options_reports_an_empty_list(
    api_client: AsyncClient, auth_header: Callable[..., dict[str, str]]
) -> None:
    assert (await detail(api_client, auth_header(role="admin"), PLAIN))["options"] == []


async def test_admin_choice_is_stored_and_becomes_the_effective_value(
    api_client: AsyncClient, auth_header: Callable[..., dict[str, str]]
) -> None:
    headers = auth_header(role="admin")

    resp = await put_options(api_client, headers, {"provider": "x_official"})

    assert resp.status_code == 200
    assert resp.json()["options"] == {"provider": "x_official"}
    body = await detail(api_client, headers)
    assert body["options"][0]["value"] == "x_official"
    assert body["options"][0]["default"] == "twitterapi_io"  # default kode tidak berubah


async def test_clearing_the_choice_goes_back_to_the_default_and_stores_null_not_an_empty_dict(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    headers = auth_header(role="admin")

    for cleared in (None, {}):
        await put_options(api_client, headers, {"provider": "x_official"})
        resp = await put_options(api_client, headers, cleared)
        assert resp.status_code == 200 and resp.json()["options"] is None
        assert (await detail(api_client, headers))["options"][0]["value"] == "twitterapi_io"
        row = await api_session.get(ScraperConfig, TWEETS)
        await api_session.refresh(row)
        assert row.options is None  # bukan {} -- satu representasi untuk "tidak ada pilihan"


async def test_a_value_that_is_not_a_declared_choice_is_rejected_and_nothing_is_stored(
    api_client: AsyncClient, auth_header: Callable[..., dict[str, str]]
) -> None:
    headers = auth_header(role="admin")

    resp = await put_options(api_client, headers, {"provider": "mastodon"})

    assert resp.status_code == 422
    assert "twitterapi_io" in resp.json()["detail"]  # pesan menyebut pilihan yang valid
    assert (await detail(api_client, headers))["config"]["options"] is None


async def test_an_undeclared_key_is_rejected(
    api_client: AsyncClient, auth_header: Callable[..., dict[str, str]]
) -> None:
    resp = await put_options(api_client, auth_header(role="admin"), {"warna": "biru"})

    assert resp.status_code == 422 and "tidak punya opsi 'warna'" in resp.json()["detail"]


async def test_a_scraper_that_declares_no_options_rejects_any(
    api_client: AsyncClient, auth_header: Callable[..., dict[str, str]]
) -> None:
    resp = await put_options(
        api_client, auth_header(role="admin"), {"provider": "x_official"}, PLAIN
    )

    assert resp.status_code == 422


async def test_only_admins_can_change_options(
    api_client: AsyncClient, auth_header: Callable[..., dict[str, str]]
) -> None:
    resp = await put_options(api_client, auth_header(role="analyst"), {"provider": "x_official"})

    assert resp.status_code == 403
    assert (await detail(api_client, auth_header(role="admin")))["config"]["options"] is None


async def test_saving_other_fields_does_not_wipe_the_stored_choice(
    api_client: AsyncClient, auth_header: Callable[..., dict[str, str]]
) -> None:
    """PUT bersifat PATCH: field yang tidak dikirim tidak boleh tersentuh."""
    headers = auth_header(role="admin")
    await put_options(api_client, headers, {"provider": "x_official"})

    resp = await api_client.put(
        f"/api/scraper/{TWEETS}/config", headers=headers, json={"max_items": 7}
    )

    assert resp.status_code == 200
    assert resp.json()["options"] == {"provider": "x_official"} and resp.json()["max_items"] == 7


async def test_reset_config_drops_the_choice_too(
    api_client: AsyncClient, auth_header: Callable[..., dict[str, str]]
) -> None:
    headers = auth_header(role="admin")
    await put_options(api_client, headers, {"provider": "x_official"})

    resp = await api_client.post(f"/api/scraper/{TWEETS}/reset-config", headers=headers)

    assert resp.status_code == 200 and resp.json()["options"] is None
    assert (await detail(api_client, headers))["options"][0]["value"] == "twitterapi_io"


async def test_a_stale_stored_choice_is_shown_as_the_default_not_as_an_error(
    api_client: AsyncClient,
    api_session: AsyncSession,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    api_session.add(ScraperConfig(scraper_id=TWEETS, enabled=True, options={"provider": "dulu"}))
    await api_session.flush()

    body = await detail(api_client, auth_header(role="admin"))

    assert body["options"][0]["value"] == "twitterapi_io"  # yang sungguh dipakai Runner


class _FakeRunner:
    """Pengganti `Runner` di endpoint dry-run: mencatat argumennya, tidak menyentuh jaringan."""

    calls: ClassVar[list[dict[str, object]]] = []

    def __init__(self, cls: type, **kwargs: object) -> None:
        type(self).calls.append({"scraper": cls.meta.id, **kwargs})  # type: ignore[attr-defined]

    def execute(self, *, trigger: str = "manual"):
        from types import SimpleNamespace

        return SimpleNamespace(status="ok", items_found=0, duration_ms=1, errors=[])


async def test_dry_run_uses_the_stored_choice_so_testing_before_switching_tests_the_right_source(
    api_client: AsyncClient,
    auth_header: Callable[..., dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("cti_scraper.runner.Runner", _FakeRunner)
    _FakeRunner.calls = []
    headers = auth_header(role="admin")

    await api_client.post(f"/api/scraper/{TWEETS}/dry-run", headers=headers)
    await put_options(api_client, headers, {"provider": "x_official"})
    resp = await api_client.post(f"/api/scraper/{TWEETS}/dry-run", headers=headers)

    assert resp.status_code == 200
    first, second = _FakeRunner.calls
    assert first["options"] == {"provider": "twitterapi_io"}  # belum memilih -> default
    assert second["options"] == {"provider": "x_official"}
    assert second["dry_run"] is True


async def test_dry_run_of_a_scraper_without_options_passes_none(
    api_client: AsyncClient,
    auth_header: Callable[..., dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("cti_scraper.runner.Runner", _FakeRunner)
    _FakeRunner.calls = []

    await api_client.post(f"/api/scraper/{PLAIN}/dry-run", headers=auth_header(role="admin"))

    assert _FakeRunner.calls[0]["options"] is None
