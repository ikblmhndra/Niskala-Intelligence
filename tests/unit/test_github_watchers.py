"""4 watcher GitHub Fase 10.E (`github_ttps`, `sophoslabs_github`,
`apt_ttp_simulation`, `mitre_github`) -- `fetch()` dijalankan lawan API GitHub palsu.

Beberapa test mengunci bug skrip lama yang SENGAJA tidak ikut ter-port:
notice cuma untuk file TERAKHIR (Sophoslab), `exit()` yang memutus run
(TTPs/Sophoslab), offset yang tercatat sebelum semua file terkirim (MITRE).
"""

from __future__ import annotations

import datetime
import json

import httpx
import pytest
from cti_scraper.errors import ParseError
from cti_scrapers.collectors.apt_ttp_simulation import AptTtpSimulation
from cti_scrapers.collectors.github_ttps import GithubTtps
from cti_scrapers.collectors.mitre_github import MitreGithub
from cti_scrapers.collectors.sophoslabs_github import SophoslabsGithub

from tests.unit.scraper_helpers import NOW, json_response, make_ctx


def commit(sha: str, days_ago: float = 1, message: str = "msg") -> dict:
    when = (NOW - datetime.timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"sha": sha, "commit": {"committer": {"date": when}, "message": message}}


def detail(sha: str, files: list[dict], message: str = "msg", days_ago: float = 1) -> dict:
    when = (NOW - datetime.timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "sha": sha,
        "html_url": f"https://github.com/o/r/commit/{sha}",
        "commit": {
            "message": message,
            "author": {"name": "Ann <a@x>", "date": when},
            "committer": {"date": when},
        },
        "files": files,
    }


def fake_github(commits: list[dict], details: dict[str, dict], *, fetched: list[str] | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/commits"):
            return json_response(commits)
        sha = path.rsplit("/", 1)[-1]
        if fetched is not None:
            fetched.append(sha)
        if sha in details:
            return json_response(details[sha])
        return json_response({"message": "Not Found"}, 404)

    return handler


def run(cls, handler, **kw):
    return list(cls().fetch(make_ctx(cls, handler, **kw)))


# --- github_ttps ---------------------------------------------------------------------


def ttp_file(name: str, status: str = "added") -> dict:
    return {"filename": name, "status": status, "blob_url": f"https://github.com/o/r/blob/x/{name}"}


def test_ttps_one_notice_per_changed_file_routed_to_the_apt_topic() -> None:
    files = [ttp_file("APT1.md"), ttp_file("APT2.md", "modified")]
    items = run(GithubTtps, fake_github([commit("aaa")], {"aaa": detail("aaa", files)}))

    assert [(i.topic, i.key) for i in items] == [("apt", "aaa:APT1.md"), ("apt", "aaa:APT2.md")]
    assert "NEW TTP POSTED ON CROCODYLI GITHUB" in items[0].text
    assert "MODIFIED TTP POSTED ON CROCODYLI GITHUB" in items[1].text
    assert '<a href="https://github.com/o/r/blob/x/APT1.md">Link</a>' in items[0].text


def test_ttps_html_in_filenames_is_escaped_so_telegram_accepts_the_message() -> None:
    files = [ttp_file("a&b<script>.md")]
    [item] = run(GithubTtps, fake_github([commit("aaa")], {"aaa": detail("aaa", files)}))

    assert "a&amp;b&lt;script&gt;.md" in item.text and "<script>" not in item.text


def test_ttps_only_the_newest_five_commits_are_inspected() -> None:
    commits = [commit(f"c{i}") for i in range(9)]
    fetched: list[str] = []
    details = {c["sha"]: detail(c["sha"], [ttp_file(f"{c['sha']}.md")]) for c in commits}

    items = run(GithubTtps, fake_github(commits, details, fetched=fetched))

    assert fetched == ["c0", "c1", "c2", "c3", "c4"] and len(items) == 5


def test_a_github_error_is_a_parse_error_not_a_keyerror() -> None:
    def rate_limited(request: httpx.Request) -> httpx.Response:
        return json_response({"message": "API rate limit exceeded"}, 403)

    with pytest.raises(ParseError, match="HTTP 403 API rate limit exceeded"):
        run(GithubTtps, rate_limited)


# --- sophoslabs_github -----------------------------------------------------------------


def sophos_file(path: str) -> dict:
    return {"filename": path, "raw_url": f"https://github.com/raw/{path}"}


def test_sophoslabs_reports_EVERY_uploaded_file_not_just_the_last() -> None:
    """Skrip lama: `send_alert_report(msg_data)` di luar loop -> cuma file terakhir."""
    files = [sophos_file("2026/09/a.pdf"), sophos_file("2026/09/b.pdf"), sophos_file("c.pdf")]
    details = {"s1": detail("s1", files, message="Add files via upload")}

    items = run(SophoslabsGithub, fake_github([commit("s1")], details))

    assert [i.key for i in items] == ["s1:2026/09/a.pdf", "s1:2026/09/b.pdf", "s1:c.pdf"]
    assert "Report Name</b>: b.pdf" in items[1].text  # bagian ke-3 path
    assert "Report Name</b>: c.pdf" in items[2].text  # path pendek -> nama file penuh
    assert {i.topic for i in items} == {"vendor_report"}


def test_sophoslabs_ignores_commits_that_are_not_uploads() -> None:
    details = {"s1": detail("s1", [sophos_file("a/b/c.pdf")], message="Update README")}

    assert run(SophoslabsGithub, fake_github([commit("s1")], details)) == []


@pytest.mark.parametrize(("days_ago", "expected"), [(5.5, 1), (6.5, 0)])
def test_sophoslabs_age_limit_matches_the_old_gt_5_days_rule(
    days_ago: float, expected: int
) -> None:
    c = commit("s1", days_ago=days_ago)
    details = {"s1": detail("s1", [sophos_file("a/b/c.pdf")], "Add files via upload", days_ago)}

    assert len(run(SophoslabsGithub, fake_github([c], details))) == expected


# --- apt_ttp_simulation -----------------------------------------------------------------


def apt_file(name: str, patch: str | None = "@@ -1 +1 @@\n context\n-old\n+new") -> dict:
    return {"filename": name, "status": "modified", "additions": 1, "deletions": 1, "patch": patch}


def test_apt_sim_readme_only_commits_are_skipped() -> None:
    d = {"r1": detail("r1", [apt_file("README.md")])}

    assert run(AptTtpSimulation, fake_github([commit("r1")], d)) == []


def test_apt_sim_sends_a_summary_with_the_filtered_patch_attached() -> None:
    d = {"a1": detail("a1", [apt_file("scen/x.py"), apt_file("scen/y.py", patch=None)], "Add scen")}

    [item] = run(AptTtpSimulation, fake_github([commit("a1")], d))

    assert item.key == "a1" and item.topic == "vendor_report"
    assert item.attachment_name == "apt_ttp_update.txt"
    assert (
        "--- PATCH for scen/x.py ---\n-old\n+new\n" in item.attachment_text
    )  # tanpa baris konteks
    assert " context" not in item.attachment_text
    assert "--- PATCH for scen/y.py ---\nNo patch available" in item.attachment_text
    assert "Ann &lt;a@x&gt;" in item.text  # author di-escape
    assert "Date</b>: September 25, 2026, 19:00:00" in item.text  # 12:00 UTC kemarin +7 = WIB


def test_apt_sim_caps_the_file_list_in_the_message_but_not_in_the_attachment() -> None:
    files = [apt_file(f"f{i}.py") for i in range(40)]
    [item] = run(AptTtpSimulation, fake_github([commit("a1")], {"a1": detail("a1", files)}))

    assert item.text.count("Filename:") == 25 and "dan 15 file lain" in item.text
    assert item.attachment_text.count("--- PATCH for") == 40
    assert len(item.text) < 4096  # muat di satu pesan Telegram


# --- mitre_github ---------------------------------------------------------------------------


def stix_bundle(created: str) -> dict:
    return {
        "objects": [
            {
                "type": "malware", "id": "malware--1", "name": "NewMal", "description": "d",
                "created": created, "x_mitre_domains": ["enterprise-attack"],
                "external_references": [
                    {"source_name": "mitre-attack", "external_id": "S9999", "url": "https://x/S9999"}
                ],
            }
        ]
    }  # fmt: skip


def mitre_handler(commits, details, bundles):
    base = fake_github(commits, details)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.startswith("/raw/"):
            return httpx.Response(200, content=json.dumps(bundles[request.url.path]))
        return base(request)

    return handler


def mitre_file(name: str, status: str = "added") -> dict:
    return {"filename": name, "status": status, "raw_url": f"https://github.com/raw/{name}"}


def test_mitre_release_commit_becomes_a_changelog_document() -> None:
    created = (NOW - datetime.timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    files = [
        mitre_file("enterprise-attack/enterprise-attack-17.1.json"),
        mitre_file("enterprise-attack/enterprise-attack-17.0.json", "modified"),  # bukan 'added'
        mitre_file("README.md"),
    ]
    commits = [commit("m1", message="Update with ATT&CK v17.1")]
    bundles = {"/raw/enterprise-attack/enterprise-attack-17.1.json": stix_bundle(created)}

    items = run(MitreGithub, mitre_handler(commits, {"m1": detail("m1", files)}, bundles))

    [item] = items
    assert item.key == "m1:enterprise-attack/enterprise-attack-17.1.json"
    assert item.attachment_name == "Mitre_ATTCK_17.1_Changelog.txt"
    assert (
        "MALWARE (1 entries)" in item.attachment_text and "NewMal (/S9999)" in item.attachment_text
    )
    assert "<b>Malware</b>: 1 entries" in item.text and "<b>Total Entries</b>: 1" in item.text
    assert "ATT&amp;CK" in item.text  # tanda & di-escape untuk HTML Telegram


@pytest.mark.parametrize(
    ("message", "days_ago", "expected"),
    [
        ("Update with ATT&CK v17.1", 1, 1),
        ("update with att&ck v17.1", 1, 1),  # tanpa peduli huruf besar
        ("Update with ATT&CK v17.1 (hotfix)", 1, 0),  # harus persis
        ("Fix typo", 1, 0),
        ("Update with ATT&CK v17.1", 7.5, 0),  # >= 7 hari dilewati
    ],
)
def test_mitre_only_recent_release_commits_are_considered(
    message: str, days_ago: float, expected: int
) -> None:
    created = (NOW - datetime.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    name = "ics-attack/ics-attack-17.1.json"
    d = {"m1": detail("m1", [mitre_file(name)], message, days_ago)}
    bundles = {f"/raw/{name}": stix_bundle(created)}

    items = run(MitreGithub, mitre_handler([commit("m1", days_ago, message)], d, bundles))

    assert len(items) == expected


def test_mitre_unparseable_bundle_is_a_parse_error() -> None:
    name = "enterprise-attack/enterprise-attack-17.1.json"
    commits = [commit("m1", message="Update with ATT&CK v17.1")]
    base = fake_github(commits, {"m1": detail("m1", [mitre_file(name)])})

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.startswith("/raw/"):
            return httpx.Response(200, content=b"<html>bukan json</html>")
        return base(request)

    with pytest.raises(ParseError, match="bukan JSON STIX"):
        run(MitreGithub, handler)
