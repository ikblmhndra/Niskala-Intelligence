"""Klasifikasi family scraper lama lewat AST (import statement), bukan
regex/heuristik teks -- matching yang sama persis dipakai buat nge-analisa
seluruh ScraperNews/ di Fase 0/eksplorasi awal.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class Family(StrEnum):
    RSS = "rss"
    """defusedxml -- ~142 dari 241 scraper lama (59%)."""
    XPATH_STATIC = "xpath_static"
    """requests + lxml -- ~11 scraper lama."""
    XPATH_BROWSER = "xpath_browser"
    """playwright -- ~45 scraper lama."""
    SELENIUM = "selenium"
    """selenium -- 8 scraper, chromedriver macOS ARM di host Linux, GAK
    PERNAH bisa jalan di produksi (lihat KNOWN_BROKEN.md). Ditulis ulang
    sebagai XPathScraper(runtime="browser"), bukan dikonversi otomatis."""
    BESPOKE = "bespoke"
    """Sisanya -- API custom, state lintas-run, atau gagal parse sama
    sekali. Porting manual lewat BaseScraper langsung."""


@dataclass
class Classification:
    path: Path
    family: Family
    imports: set[str] = field(default_factory=set)
    parse_error: str | None = None


def _top_level_imports(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def classify_file(path: Path) -> Classification:
    try:
        tree = ast.parse(path.read_text(errors="ignore"), filename=str(path))
    except SyntaxError as e:
        return Classification(path=path, family=Family.BESPOKE, parse_error=str(e))

    imports = _top_level_imports(tree)

    if "selenium" in imports:
        family = Family.SELENIUM
    elif "playwright" in imports:
        family = Family.XPATH_BROWSER
    elif "defusedxml" in imports:
        family = Family.RSS
    elif "lxml" in imports and "requests" in imports:
        family = Family.XPATH_STATIC
    else:
        family = Family.BESPOKE

    return Classification(path=path, family=family, imports=imports)


def classify_dir(scrapers_dir: Path, *, only: set[str] | None = None) -> list[Classification]:
    """`only`: batasi ke stem file tertentu (mis. job aktif Rundeck).
    `None` = semua .py langsung di bawah `scrapers_dir` (bukan
    backup_script/, stopped_script/, modules/, dst)."""
    results = []
    for p in sorted(scrapers_dir.glob("*.py")):
        if only is not None and p.stem not in only:
            continue
        results.append(classify_file(p))
    return results
