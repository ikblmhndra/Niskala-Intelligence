"""Port dari `ScraperNewsWeb/app/routers/changelog.py` -- baca+parse
`CHANGELOG.md` langsung dari disk, gak nyentuh DB sama sekali (logic-nya
gak berubah dari legacy). Path dicari relatif ke root repo (bukan hitung
`.parent` tetap N kali kayak legacy) -- pola sama kayak `_find_repo_root()`
di `tests/integration/conftest.py`, lebih tahan kalau struktur direktori
`apps/api` berubah."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from cti_api.deps import require_auth

router = APIRouter(
    prefix="/api/changelog", tags=["changelog"], dependencies=[Depends(require_auth)]
)

_HEADER_RE = re.compile(r"^## \[([^\]]+)\]\s*-\s*(.+)$", re.MULTILINE)


def _find_changelog_path() -> Path:
    p = Path(__file__).resolve()
    while not (p / "CHANGELOG.md").exists():
        if p.parent == p:
            raise RuntimeError("CHANGELOG.md gak ketemu di parent mana pun")
        p = p.parent
    return p / "CHANGELOG.md"


def _parse() -> list[dict[str, str]]:
    text = _find_changelog_path().read_text(encoding="utf-8")
    matches = list(_HEADER_RE.finditer(text))
    entries = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        # `.strip("-")` (bukan literal "---") -- strip charset {'-'} dari
        # kedua ujung, buang separator markdown `---` sisa antar-entry.
        # Port apa adanya dari legacy, cuma diperjelas biar gak ke-flag
        # ruff B005 (charset vs literal substring keliatan mirip).
        content = text[start:end].strip().strip("-").strip()
        entries.append(
            {"version": m.group(1).strip(), "date": m.group(2).strip(), "content": content}
        )
    return entries


@router.get("")
async def list_versions() -> list[dict[str, str]]:
    return [{"version": e["version"], "date": e["date"]} for e in _parse()]


@router.get("/{version}")
async def get_version(version: str) -> dict[str, str]:
    for e in _parse():
        if e["version"] == version:
            return e
    raise HTTPException(status_code=404, detail="Version not found")
