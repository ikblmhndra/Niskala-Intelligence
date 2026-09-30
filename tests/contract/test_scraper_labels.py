"""Label scraper yang tampil ke analis (`source` di artikel/Telegram) dan kunci
migrasi dari sistem lama (`legacy_script`/`legacy_label`) harus bermakna dan unik.

Latar: `blackberryThreat.py` lama nge-push label templat "NEW ARTICLE FROM NAME"
(placeholder yang gak pernah diganti), dan codemod memindahkannya apa adanya
jadi `source="Name"` -- artikel BlackBerry bakal tampil bersumber dari "Name".
`legacy_script`/`legacy_label` yang bentrok bikin warm start (`tools/seed/
fase10_warm_start.py`) salah-petakan riwayat dedup ke scraper yang keliru.
"""

from __future__ import annotations

from collections import Counter

from cti_scraper import registry

PLACEHOLDERS = {"", "name", "source", "title", "label", "example", "test", "todo"}


def test_no_scraper_ships_a_placeholder_source_label() -> None:
    bad = {
        sid: cls.meta.source
        for sid, cls in registry.discover().items()
        if cls.meta.source.strip().lower() in PLACEHOLDERS
    }

    assert bad == {}


def test_source_labels_are_unique_ignoring_case() -> None:
    counts = Counter(cls.meta.source.strip().lower() for cls in registry.discover().values())

    assert {s: n for s, n in counts.items() if n > 1} == {}


def test_legacy_keys_are_unique_when_present() -> None:
    reg = registry.discover().values()
    scripts = Counter(c.meta.legacy_script for c in reg if c.meta.legacy_script)
    labels = Counter(c.meta.legacy_label for c in reg if c.meta.legacy_label)

    assert {k: n for k, n in {**scripts, **labels}.items() if n > 1} == {}
