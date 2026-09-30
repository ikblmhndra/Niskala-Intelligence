"""Jaga-jaga build Docker (Fase 10.B) yang gagalnya baru ketahuan pas deploy.

1. Pin `playwright` di Dockerfile == versi di `uv.lock`. Chromium di image
   di-install lewat `ARG PLAYWRIGHT_VERSION` (layer terpisah dari venv biar
   gak ke-download ulang tiap source berubah); kalau `uv.lock` naik dan ARG
   ketinggalan, revisi browser beda -> "Executable doesn't exist" di worker.
   (Build juga gagal lewat smoke launch, tapi test ini nangkepnya di PR.)
2. Stage `browser-base` IDENTIK di api.Dockerfile dan worker.Dockerfile --
   kalau beda satu karakter, layer Chromium (~600MB) gak lagi dishare cache.
3. `.dockerignore` tetap ngeblok secret/data prod -- checklist cutover:
   "gak ada secret di layer image".
"""

from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
DOCKERFILES = ("api.Dockerfile", "worker.Dockerfile")


def _locked_playwright_version() -> str:
    lock = (ROOT / "uv.lock").read_text()
    m = re.search(r'\[\[package\]\]\nname = "playwright"\nversion = "([^"]+)"', lock)
    assert m, "playwright gak ketemu di uv.lock"
    return m.group(1)


def _browser_base_block(text: str) -> str:
    m = re.search(r"^FROM \$\{PYTHON_IMAGE\} AS browser-base\n(?:(?!^# -{5,}).*\n)+", text, re.M)
    assert m, "stage browser-base gak ketemu"
    return m.group(0)


def test_dockerfile_playwright_pin_matches_uv_lock() -> None:
    locked = _locked_playwright_version()
    for name in DOCKERFILES:
        text = (ROOT / "docker" / name).read_text()
        m = re.search(r"^ARG PLAYWRIGHT_VERSION=(\S+)$", text, re.M)
        assert m, f"{name}: ARG PLAYWRIGHT_VERSION gak ada"
        assert m.group(1) == locked, (
            f"{name} nge-pin playwright {m.group(1)} tapi uv.lock {locked} -- "
            "samain ARG-nya (di api.Dockerfile DAN worker.Dockerfile)"
        )


def test_browser_base_stage_identical_across_dockerfiles() -> None:
    blocks = [_browser_base_block((ROOT / "docker" / name).read_text()) for name in DOCKERFILES]
    assert blocks[0] == blocks[1], (
        "browser-base beda antara api & worker -> cache layer gak dishare"
    )


def test_dockerignore_blocks_secrets_and_prod_data() -> None:
    lines = {
        ln.strip()
        for ln in (ROOT / ".dockerignore").read_text().splitlines()
        if ln.strip() and not ln.startswith("#")
    }
    for must in (".env", ".env.*", "legacy/", "tools/salvage/", "tests/fixtures/", ".git"):
        assert must in lines, f".dockerignore harus ngeblok `{must}`"
    # .env.example boleh (isinya cuma placeholder), yang lain gak.
    assert "!.env.example" in lines
