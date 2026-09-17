"""Fase 1: workspace-nya nyambung.

Bukan placeholder buat nutup exit code pytest -- ini test regresi beneran:
kalau salah satu dari 4 package berhenti bisa di-import (pyproject.toml
rusak, __init__.py kehapus, workspace member ke-drop), test ini merah duluan
sebelum kena di fase berikutnya yang pakai package-package ini.
"""

import cti_alerts
import cti_core
import cti_enrich
import cti_scraper


def test_all_workspace_packages_importable() -> None:
    for pkg in (cti_core, cti_scraper, cti_enrich, cti_alerts):
        assert hasattr(pkg, "__version__")
