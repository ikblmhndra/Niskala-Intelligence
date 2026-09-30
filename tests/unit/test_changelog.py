"""Unit test router `changelog.py` -- baca+parse `CHANGELOG.md` dari disk,
gak butuh DB. Fase 7.3."""

from __future__ import annotations

from pathlib import Path

import pytest
from cti_api.routers.changelog import _find_changelog_path, _parse


def test_find_changelog_path_locates_repo_root_file() -> None:
    path = _find_changelog_path()
    assert path.name == "CHANGELOG.md"
    assert path.exists()


def test_parse_real_changelog_has_initial_version() -> None:
    entries = _parse()
    assert len(entries) >= 1
    versions = [e["version"] for e in entries]
    assert "0.1.0" in versions


def test_parse_real_changelog_entry_has_date_and_content() -> None:
    entries = _parse()
    first = next(e for e in entries if e["version"] == "0.1.0")
    assert first["date"] == "2026-09-18"
    assert len(first["content"]) > 0
    assert not first["content"].startswith("-")
    assert not first["content"].endswith("-")


def test_parse_handles_multiple_versions_and_dash_separators(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        "# Changelog\n\n"
        "## [0.2.0] - 2026-10-01\n"
        "- Fitur baru B\n"
        "---\n"
        "## [0.1.0] - 2026-09-18\n"
        "- Fitur awal A\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("cti_api.routers.changelog._find_changelog_path", lambda: changelog)

    entries = _parse()
    assert [e["version"] for e in entries] == ["0.2.0", "0.1.0"]
    assert entries[0]["date"] == "2026-10-01"
    assert entries[0]["content"] == "Fitur baru B"
    assert entries[1]["content"] == "Fitur awal A"
