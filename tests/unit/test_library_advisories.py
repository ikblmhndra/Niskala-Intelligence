"""`techstack_npm/pypi/go` (Fase 10.E) -- advisory library lewat deps.dev + osv.dev palsu.

Mengunci empat bug skrip lama yang sengaja tidak ikut ter-port (notice hanya
untuk advisory TERAKHIR per versi, urut versi sebagai string, pencocokan versi
mentah vs ternormalisasi, dan `details` tanpa batas/escape).
"""

from __future__ import annotations

import httpx
import pytest
from cti_scraper.errors import ParseError
from cti_scraper.families.library_advisories import version_key
from cti_scrapers.collectors.techstack_go import TechstackGo
from cti_scrapers.collectors.techstack_npm import TechstackNpm

from tests.unit.scraper_helpers import json_response, make_ctx


def advisory(adv_id: str, modified: str = "2024-02-16T14:08:53.123456Z", **over: object) -> dict:
    base = {
        "id": adv_id,
        "details": f"detail {adv_id}",
        "aliases": [f"CVE-{adv_id[-4:]}"],
        "published": "2024-01-01T00:00:00Z",
        "modified": modified,
        "affected": [{"ranges": [{"events": [{"introduced": "0"}, {"fixed": "1.2.3"}]}]}],
    }
    return {**base, **over}


class DepsDev:
    """deps.dev + osv.dev palsu, mencatat request."""

    def __init__(self, versions: dict[str, list[str]], by_version: dict, osv: dict) -> None:
        self.versions, self.by_version, self.osv = versions, by_version, osv
        self.requests: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        raw = request.url.raw_path.decode()
        self.requests.append(raw)
        if request.url.host == "api.osv.dev":
            adv_id = raw.rsplit("/", 1)[-1]
            return json_response(self.osv[adv_id]) if adv_id in self.osv else json_response({}, 404)
        if "/versions/" in raw:
            pkg, ver = raw.split("/packages/")[1].split("/versions/")
            return json_response(
                {"advisoryKeys": [{"id": a} for a in self.by_version.get((pkg, ver), [])]}
            )
        pkg = raw.split("/packages/")[1]
        if pkg not in self.versions:
            return json_response({"error": "not found"}, 404)
        return json_response(
            {
                "versions": [
                    {"versionKey": {"system": "NPM", "name": pkg, "version": v}}
                    for v in self.versions[pkg]
                ]
            }
        )


def run(cls, fake, **kw):
    return list(cls().fetch(make_ctx(cls, fake, **kw)))


class OnePackage(TechstackNpm):
    """NPM dengan SATU paket, biar test fokus."""

    __abstract__ = True
    packages = ("lodash",)


def test_version_key_orders_numerically_not_alphabetically() -> None:
    assert version_key("1.10.0") > version_key("1.9.0")
    assert version_key("v1.2.3") == version_key("1.2.3")
    assert version_key("1.0.0-beta") == version_key("1.0.0")
    assert sorted(["1.9", "1.10", "1.2"], key=version_key) == ["1.2", "1.9", "1.10"]


def test_only_the_five_latest_versions_are_inspected_by_numeric_order() -> None:
    versions = ["1.2.0", "1.9.0", "1.10.0", "2.0.0", "0.9.0", "1.11.0", "0.1.0"]
    fake = DepsDev({"lodash": versions}, {}, {})

    run(OnePackage, fake)

    inspected = [r.split("/versions/")[1] for r in fake.requests if "/versions/" in r]
    assert inspected == [
        "2.0.0",
        "1.11.0",
        "1.10.0",
        "1.9.0",
        "1.2.0",
    ]  # 0.9.0 dan 0.1.0 tersingkir


def test_every_advisory_of_a_version_is_reported_not_just_the_last() -> None:
    """Skrip lama membangun pesan SETELAH loop -> cuma advisory terakhir yang terkirim."""
    fake = DepsDev(
        {"lodash": ["4.17.21"]},
        {("lodash", "4.17.21"): ["GHSA-aaaa-0001", "GHSA-bbbb-0002", "GHSA-cccc-0003"]},
        {a: advisory(a) for a in ["GHSA-aaaa-0001", "GHSA-bbbb-0002", "GHSA-cccc-0003"]},
    )

    items = run(OnePackage, fake)

    assert [i.key for i in items] == [
        "GHSA-aaaa-0001:2024-02-16", "GHSA-bbbb-0002:2024-02-16", "GHSA-cccc-0003:2024-02-16",
    ]  # fmt: skip
    assert all(i.topic == "library_advisory" for i in items)


def test_an_advisory_shared_by_many_versions_is_fetched_and_reported_once() -> None:
    fake = DepsDev(
        {"lodash": ["4.17.21", "4.17.20", "4.17.19"]},
        {("lodash", v): ["GHSA-aaaa-0001"] for v in ["4.17.21", "4.17.20", "4.17.19"]},
        {"GHSA-aaaa-0001": advisory("GHSA-aaaa-0001")},
    )

    items = run(OnePackage, fake)

    assert len(items) == 1
    assert sum("api.osv.dev" in r or "/v1/vulns/" in r for r in fake.requests) == 1


def test_dedup_key_matches_the_legacy_offset_identity() -> None:
    """`AdvisoryID` + `ModifiedDate` (YYYY-MM-DD) -- sama dengan `techstack_*_offset.txt`."""
    fake = DepsDev(
        {"lodash": ["1.0.0"]},
        {("lodash", "1.0.0"): ["GHSA-x"]},
        {"GHSA-x": advisory("GHSA-x", modified="2024-07-15T09:00:00Z")},
    )

    [item] = run(OnePackage, fake)

    assert item.key == "GHSA-x:2024-07-15"


def test_fixed_version_is_the_numerically_highest_and_missing_fix_is_na() -> None:
    fixed = [{"ranges": [{"events": [{"fixed": "1.9.0"}]}, {"events": [{"fixed": "1.10.0"}]}]}]
    fake = DepsDev(
        {"lodash": ["1.0.0"]},
        {("lodash", "1.0.0"): ["GHSA-a", "GHSA-b"]},
        {"GHSA-a": advisory("GHSA-a", affected=fixed), "GHSA-b": advisory("GHSA-b", affected=[])},
    )

    a, b = run(OnePackage, fake)

    assert "Fixed Version</b> : 1.10.0" in a.text and "Lower than 1.10.0 Version" in a.text
    assert "Fixed Version</b> : N/A" in b.text and "Affected Version</b> : N/A" in b.text


def test_long_html_details_are_escaped_and_truncated_to_fit_telegram() -> None:
    fake = DepsDev(
        {"lodash": ["1.0.0"]},
        {("lodash", "1.0.0"): ["GHSA-x"]},
        {"GHSA-x": advisory("GHSA-x", details="<script>alert(1)</script>" + "y" * 9000)},
    )

    [item] = run(OnePackage, fake)

    assert "&lt;script&gt;" in item.text and "<script>" not in item.text
    assert len(item.text) < 4096 and "..." in item.text


def test_an_advisory_that_osv_does_not_know_is_skipped_not_fatal() -> None:
    fake = DepsDev(
        {"lodash": ["1.0.0"]},
        {("lodash", "1.0.0"): ["GHSA-gone", "GHSA-ok"]},
        {"GHSA-ok": advisory("GHSA-ok")},
    )

    assert [i.key for i in run(OnePackage, fake)] == ["GHSA-ok:2024-02-16"]


def test_unknown_package_is_a_visible_parse_error() -> None:
    with pytest.raises(ParseError, match="HTTP 404"):
        run(OnePackage, DepsDev({}, {}, {}))


def test_go_module_paths_are_percent_encoded_and_prefixed_versions_still_match() -> None:
    class OneGo(TechstackGo):
        __abstract__ = True
        packages = ("github.com/docker/docker",)

    enc = "github.com%2Fdocker%2Fdocker"
    fake = DepsDev(
        {enc: ["v25.0.1", "v24.0.7"]},
        {(enc, "v25.0.1"): ["GHSA-go"]},
        {"GHSA-go": advisory("GHSA-go")},
    )

    [item] = run(OneGo, fake)

    assert any(f"/systems/go/packages/{enc}" in r for r in fake.requests)
    assert "NEW ADVISORYS UPDATE FOR GOLANG" in item.text
    assert "<b>Name</b> : github.com/docker/docker" in item.text  # nama tampil tidak ter-encode


def test_per_run_cap_limits_notices_and_the_rest_wait_for_the_next_run() -> None:
    ids = [f"GHSA-{n:04d}" for n in range(30)]
    fake = DepsDev({"lodash": ["1.0.0"]}, {("lodash", "1.0.0"): ids}, {a: advisory(a) for a in ids})

    assert len(run(OnePackage, fake)) == OnePackage.meta.max_items == 15
