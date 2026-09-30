"""`tools/ops/scrub_fixtures.py` -- scrub secret-lookalike dari fixture rekaman."""

from __future__ import annotations

import json

from tools.ops import scrub_fixtures as sf

AWS = "AKIAABCDEFGHIJKLMNOP"  # gitleaks:allow
KEY = "b7f3a9c2e1d84f6a90b3c5d7e2f1a4b6"  # gitleaks:allow


def report(*items: tuple[str, str]) -> list[dict]:
    return [{"File": f, "Secret": s, "RuleID": "x", "StartLine": 1} for f, s in items]


def test_placeholder_keeps_length_and_matches_no_token_shape() -> None:
    for secret in (AWS, KEY, "abc", "x"):
        out = sf.placeholder(secret)
        assert len(out) == len(secret)
    assert sf.placeholder(AWS) == "REDACTED" + "_" * 12
    assert not sf.placeholder(AWS).startswith("AKIA")


def test_every_occurrence_in_the_file_is_replaced_not_only_the_reported_line(tmp_path) -> None:
    f = tmp_path / "a" / "page.html"
    f.parent.mkdir()
    f.write_text(f'<a data-key="{KEY}"></a>\n<script>var k="{KEY}"; var a="{AWS}";</script>\n')

    replaced, warnings = sf.scrub(report(("a/page.html", KEY), ("a/page.html", AWS)), root=tmp_path)

    text = f.read_text()
    assert (replaced, warnings) == (3, [])
    assert KEY not in text and AWS not in text
    assert text.count("REDACTED") == 3
    assert text.startswith('<a data-key="REDACTED')  # sisa dokumen utuh


def test_strip_prefix_maps_docker_paths_and_only_that_file_changes(tmp_path) -> None:
    (tmp_path / "x.xml").write_text(f"<t>{AWS}</t>")
    (tmp_path / "y.xml").write_text(f"<t>{AWS}</t>")  # gak dilaporkan -> jangan disentuh

    sf.scrub(report(("/src/x.xml", AWS)), root=tmp_path, strip_prefix="/src")

    assert AWS not in (tmp_path / "x.xml").read_text()
    assert (tmp_path / "y.xml").read_text() == f"<t>{AWS}</t>"


def test_longer_secret_containing_a_shorter_one_is_replaced_whole(tmp_path) -> None:
    f = tmp_path / "f.txt"
    f.write_text(f"{KEY}{KEY}")
    short, long_ = KEY, KEY + KEY

    sf.scrub(report(("f.txt", short), ("f.txt", long_)), root=tmp_path)

    assert f.read_text() == sf.placeholder(long_)  # bukan dua potongan setengah-ganti


def test_rerun_is_a_noop_and_dry_run_writes_nothing(tmp_path) -> None:
    f = tmp_path / "f.html"
    f.write_text(f"k={KEY}")

    replaced, _ = sf.scrub(report(("f.html", KEY)), root=tmp_path, dry_run=True)
    assert replaced == 1 and f.read_text() == f"k={KEY}"

    sf.scrub(report(("f.html", KEY)), root=tmp_path)
    again, _ = sf.scrub(report(("f.html", KEY)), root=tmp_path)
    assert again == 0


def test_missing_file_is_a_warning_and_a_nonzero_exit(tmp_path) -> None:
    rep = tmp_path / "r.json"
    rep.write_text(json.dumps(report(("ghost.html", KEY))))

    code = sf.main([str(rep), "--root", str(tmp_path)])

    assert code == 1


def test_non_utf8_bytes_survive_scrubbing(tmp_path) -> None:
    f = tmp_path / "bin.html"
    f.write_bytes(b"\xff\xfe<p>" + KEY.encode() + b"</p>\x80")

    sf.scrub(report(("bin.html", KEY)), root=tmp_path)

    data = f.read_bytes()
    assert data.startswith(b"\xff\xfe<p>REDACTED") and data.endswith(b"</p>\x80")
