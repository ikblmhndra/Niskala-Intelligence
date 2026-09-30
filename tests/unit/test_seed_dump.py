"""`tools/seed/_dump.py` -- pembaca dump buat script seed Fase 10."""

from __future__ import annotations

import pytest

from tools.seed._dump import DirDump, DumpError, MemoryDump


def test_missing_collection_file_is_an_explicit_error(tmp_path) -> None:
    with pytest.raises(DumpError, match="news_db/clients"):
        DirDump(tmp_path).docs("news_db/clients")


def test_memory_dump_returns_copies_and_treats_unknown_collections_as_empty() -> None:
    dump = MemoryDump({"a/b": [{"x": 1}]})

    first = dump.docs("a/b")
    first[0]["x"] = 99  # mutasi hasil gak boleh bocor ke pembacaan berikutnya

    assert dump.docs("a/b") == [{"x": 1}]
    assert dump.docs("a/tidak-ada") == []
