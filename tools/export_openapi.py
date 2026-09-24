"""Ekspor skema OpenAPI `create_app()` ke `docs/openapi.json` -- Fase 7.7.

Artifact statis ini yang bakal dibaca `openapi-typescript` buat generate
client TypeScript pas Fase 8 (`apps/web`, lihat plan §9) -- drift
frontend-backend ketahuan saat compile, bukan pas runtime. Di-commit ke
git (bukan `.gitignore`) supaya diff-nya kelihatan di code review tiap
kali kontrak endpoint berubah.

Murni introspeksi statis -- `app.openapi()` baca route/Pydantic model
doang, gak pernah connect ke Postgres/Redis beneran walau `create_app()`
butuh `Settings` valid buat kebentuk (lihat `_ensure_placeholder_env()`).
Aman dijalanin di mana aja (dev lokal TANPA `.env`, CI TANPA testcontainer)
-- gak ada dependency eksternal.

Jalanin:

    uv run python tools/export_openapi.py
"""

from __future__ import annotations

import json
import os
import pathlib
from typing import Any

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
_OUTPUT = _REPO_ROOT / "docs" / "openapi.json"


def _ensure_placeholder_env() -> None:
    """4 field WAJIB tanpa default di `Settings` (`database.url`/
    `sync_url`, `auth.jwt_secret`/`session_secret_key`, lihat
    `cti_core.config`) -- nilai di sini gak pernah kepake buat I/O
    beneran (lihat docstring modul), cuma biar `Settings()` gak raise
    validation error pas `create_app()` dipanggil. `setdefault` --
    env var asli (kalau proses ini kebetulan jalan di shell yang udah
    di-export) tetap menang."""
    os.environ.setdefault("DATABASE__URL", "postgresql+asyncpg://placeholder/placeholder")
    os.environ.setdefault("DATABASE__SYNC_URL", "postgresql+psycopg://placeholder/placeholder")
    os.environ.setdefault("AUTH__JWT_SECRET", "openapi-export-placeholder")
    os.environ.setdefault("AUTH__SESSION_SECRET_KEY", "openapi-export-placeholder")


def export_schema() -> dict[str, Any]:
    """`create_app()` diimpor DI DALAM fungsi ini (bukan di top-level
    modul) -- `cti_api/main.py` punya `app = create_app()` di level
    modul, jadi butuh env placeholder ke-set DULU sebelum import
    ke-trigger."""
    _ensure_placeholder_env()
    from cti_api.main import create_app

    return create_app().openapi()


def main() -> None:
    schema = export_schema()
    _OUTPUT.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
    print(f"OpenAPI schema exported to {_OUTPUT} ({len(schema.get('paths', {}))} paths)")


if __name__ == "__main__":
    main()
