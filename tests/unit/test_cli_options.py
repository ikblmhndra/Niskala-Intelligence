"""CLI `cti-scraper dry-run|run --option key=value` -- timpa opsi scraper SEKALI JALAN
(mis. coba sumber Twitter lain di staging) tanpa mengubah konfigurasi control plane."""

from __future__ import annotations

from types import SimpleNamespace
from typing import ClassVar

import pytest
from cti_scraper.cli.main import _parse_options, app
from typer.testing import CliRunner

cli = CliRunner()
TWITTER = "trending_cve"  # punya opsi `provider`, tanpa reference_data -> dry-run tanpa DB


class FakeRunner:
    calls: ClassVar[list[dict[str, object]]] = []

    def __init__(self, cls: type, **kwargs: object) -> None:
        type(self).calls.append({"scraper": cls.meta.id, **kwargs})  # type: ignore[attr-defined]

    def execute(self, *, trigger: str = "manual") -> SimpleNamespace:
        return SimpleNamespace(status="ok", items_found=3, duration_ms=5, errors=[])


@pytest.fixture
def fake_runner(monkeypatch: pytest.MonkeyPatch) -> type[FakeRunner]:
    FakeRunner.calls = []
    monkeypatch.setattr("cti_scraper.runner.Runner", FakeRunner)
    return FakeRunner


def test_parse_options_splits_on_the_first_equals_and_trims() -> None:
    assert _parse_options(["provider=x_official", " a = b=c "]) == {
        "provider": "x_official",
        "a": "b=c",
    }
    assert _parse_options([]) == {}


@pytest.mark.parametrize("bad", ["provider", "=x_official", "  =x"])
def test_malformed_option_pairs_are_usage_errors(bad: str) -> None:
    result = cli.invoke(app, ["dry-run", TWITTER, "--option", bad])

    assert result.exit_code == 2 and "key=value" in result.output


def test_dry_run_forwards_the_options_to_the_runner(fake_runner: type[FakeRunner]) -> None:
    result = cli.invoke(app, ["dry-run", TWITTER, "-o", "provider=x_official"])

    assert result.exit_code == 0, result.output
    assert fake_runner.calls == [
        {"scraper": TWITTER, "dry_run": True, "options": {"provider": "x_official"}}
    ]
    assert "status=ok items_found=3" in result.output


def test_a_value_the_scraper_does_not_offer_is_rejected_with_the_valid_choices() -> None:
    result = cli.invoke(app, ["dry-run", TWITTER, "--option", "provider=mastodon"])

    assert result.exit_code == 2
    assert "opsi ditolak" in result.output and "twitterapi_io" in result.output


def test_an_unknown_option_key_is_rejected() -> None:
    result = cli.invoke(app, ["dry-run", TWITTER, "--option", "warna=biru"])

    assert result.exit_code == 2 and "tidak punya opsi 'warna'" in result.output
