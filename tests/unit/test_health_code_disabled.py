"""`compute_health` untuk scraper yang dimatikan di KODE (`meta.enabled=False`).

Ketemu 2026-10-01 setelah waiver census: 5 scraper di-waive lewat `enabled=False` di meta, beat
melewati mereka, tapi `GET /api/scraper/health` tetap menghitungnya `degraded` (run terakhir
`parse_error` lama) lalu `dead` -- noise permanen di banner `/scrapers` dan digest Telegram.
Aturan "siapa yang dimatikan" harus SAMA dengan `cti_worker.beat`: baris config menang, kalau
tidak ada baru `meta.enabled`."""

from __future__ import annotations

import datetime
from types import SimpleNamespace
from typing import Any, cast

import pytest
from cti_scraper.base import ScraperMeta
from cti_scraper.health import compute_health, summarize_fleet_health

UTC = datetime.UTC
NOW = datetime.datetime(2026, 10, 1, 12, 45, tzinfo=UTC)


def _meta(*, enabled: bool = True) -> ScraperMeta:
    return ScraperMeta(
        id="x",
        source="X",
        schedule="*/15 * * * *",
        enabled=enabled,
        legacy_label="X",
        legacy_script="x",
    )


def _run(status: str, *, minutes_ago: int = 5) -> Any:
    return SimpleNamespace(status=status, started_at=NOW - datetime.timedelta(minutes=minutes_ago))


def _config(*, enabled: bool) -> Any:
    return SimpleNamespace(enabled=enabled, schedule=None)


@pytest.mark.parametrize("last_status", ["parse_error", "ok", "empty"])
def test_meta_disabled_tanpa_config_tampil_disabled(last_status: str) -> None:
    runs = [_run(last_status)]
    assert compute_health(_meta(enabled=False), None, runs, now=NOW) == "disabled"


def test_meta_disabled_run_terakhir_sudah_lama_tetap_disabled_bukan_dead() -> None:
    runs = [_run("parse_error", minutes_ago=60 * 24 * 3)]
    assert compute_health(_meta(enabled=False), None, runs, now=NOW) == "disabled"


def test_meta_disabled_tanpa_run_sama_sekali_disabled_bukan_stale() -> None:
    assert compute_health(_meta(enabled=False), None, [], now=NOW) == "disabled"


def test_config_enabled_menang_atas_meta_disabled() -> None:
    """Operator menyalakan lagi lewat control plane -> beat menjadwalkannya, health menilainya."""
    runs = [_run("parse_error")]
    got = compute_health(_meta(enabled=False), _config(enabled=True), runs, now=NOW)
    assert got == "degraded"


def test_config_disabled_menang_atas_meta_enabled() -> None:
    runs = [_run("ok")]
    assert compute_health(_meta(enabled=True), _config(enabled=False), runs, now=NOW) == "disabled"


def test_meta_enabled_tanpa_config_dinilai_normal() -> None:
    assert compute_health(_meta(), None, [_run("parse_error")], now=NOW) == "degraded"
    assert compute_health(_meta(), None, [_run("ok")], now=NOW) == "ok"
    assert compute_health(_meta(), None, [], now=NOW) == "stale"


def test_summarize_fleet_health_menandai_waiver_disabled() -> None:
    registry = {
        "live": cast(Any, SimpleNamespace(meta=_meta())),
        "waived": cast(Any, SimpleNamespace(meta=_meta(enabled=False))),
    }
    runs = {"live": [_run("ok")], "waived": [_run("parse_error")]}
    entries = {e.scraper_id: e.status for e in summarize_fleet_health(registry, {}, runs, now=NOW)}
    assert entries == {"live": "ok", "waived": "disabled"}
