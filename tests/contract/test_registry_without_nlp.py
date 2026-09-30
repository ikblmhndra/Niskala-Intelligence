"""Registry harus bisa di-`discover()` TANPA extra `nlp` (spaCy/sumy/nltk).

SETIAP proses -- API (`/api/scraper/*`), worker, beat (`build_beat_schedule`)
-- nge-`discover()` seluruh registry pas start. Image `api` dan `worker`
(ringan) sengaja gak bawa spaCy (docker/*.Dockerfile), jadi satu modul scraper
yang meng-import spaCy di level atas = SEMUA proses itu gagal start. Di dev
gak pernah kelihatan karena env dev selalu install `--extra nlp`; ketauan
pertama kali pas build image `worker` Fase 10.B (`monitor_x` -> `stages.score`
-> `import spacy`).

Subprocess + `sys.modules[nama] = None` (bikin `import nama` raise
ImportError) niru image tanpa extra itu, tanpa harus nge-uninstall apa pun.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

BLOCKED = ("spacy", "sumy", "nltk", "torch", "transformers")


def test_registry_discovers_without_nlp_extra() -> None:
    code = textwrap.dedent(
        f"""
        import sys
        for name in {BLOCKED!r}:
            sys.modules[name] = None
        from cti_scraper.registry import discover
        registry = discover(force=True)
        assert len(registry) > 50, f"cuma {{len(registry)}} scraper ke-discover"
        print(len(registry))
        """
    )

    proc = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=180, check=False
    )

    assert proc.returncode == 0, f"discover() gagal tanpa extra nlp:\n{proc.stderr[-3000:]}"


def _run_without_nlp(code: str) -> subprocess.CompletedProcess[str]:
    prelude = f"import sys\nfor name in {BLOCKED!r}:\n    sys.modules[name] = None\n"
    return subprocess.run(
        [sys.executable, "-c", prelude + textwrap.dedent(code)],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )


def test_enrich_pipeline_imports_without_nlp_extra() -> None:
    """`cti_enrich.pipeline` harus bisa di-import tanpa nltk/sumy/spaCy: test
    ketahanan pipeline men-stub semua stage, jadi di CI (`--extra dev`, tanpa
    extra `nlp`) mereka gak butuh library itu -- dulu `stages/summarize.py`
    meng-import `nltk` di level modul dan seluruh sesi pytest mati saat collection."""
    proc = _run_without_nlp("from cti_enrich import pipeline; print(pipeline.run_pipeline)")

    assert proc.returncode == 0, f"import pipeline gagal tanpa extra nlp:\n{proc.stderr[-3000:]}"


def test_summarize_fails_loudly_when_the_nlp_dependency_is_missing() -> None:
    """Kebalikannya: import lazy GAK boleh berubah jadi 'ringkasan = teks asli'
    diam-diam. `summarize()` menelan exception parse, tapi dependency yang
    hilang harus tetap meledak (image produksi yang kelupaan extra `nlp`)."""
    proc = _run_without_nlp(
        """
        from cti_enrich.stages.summarize import summarize
        try:
            summarize("Kalimat satu. Kalimat dua.")
        except ImportError:
            print("IMPORTERROR")
        else:
            print("DITELAN")
        """
    )

    assert proc.returncode == 0, proc.stderr[-2000:]
    assert proc.stdout.strip() == "IMPORTERROR"
