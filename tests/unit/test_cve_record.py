"""`cti_worker.reports.cve_record` -- ringkasan record MITRE buat laporan Top CVE."""

from __future__ import annotations

import httpx
import pytest
from cti_worker.reports.cve_record import (
    applicable_to_stack,
    base_score,
    fetch_record,
    product_vendor,
    score_category,
    summarize,
)


def metric(score: float, key: str = "cvssV3_1") -> dict:
    return {key: {"baseScore": score, "vectorString": "CVSS:3.1/AV:N"}}


def record(cna_metrics=None, adp=None, cna_affected=None) -> dict:
    cna: dict = {}
    if cna_metrics is not None:
        cna["metrics"] = cna_metrics
    if cna_affected is not None:
        cna["affected"] = cna_affected
    return {"containers": {"cna": cna, "adp": adp or []}}


@pytest.mark.parametrize(
    ("score", "cat"),
    [(None, "None"), (0.0, "None"), (0.1, "None"), (0.13, "Low"), (3.9, "Low"), (4.0, "Medium"),
     (6.9, "Medium"), (7.0, "High"), (8.9, "High"), (9.0, "Critical"), (10.0, "Critical")],
)  # fmt: skip
def test_score_categories_match_the_old_thresholds(score, cat) -> None:
    assert score_category(score) == cat


def test_base_score_is_the_highest_across_metrics_and_versions() -> None:
    rec = record(cna_metrics=[metric(5.5), metric(9.8, "cvssV4_0"), {"other": {"content": "x"}}])

    assert base_score(rec) == 9.8


def test_base_score_falls_back_to_adp_when_cna_has_no_score() -> None:
    rec = record(cna_metrics=[{"other": {"content": "x"}}], adp=[{"metrics": [metric(7.5)]}])

    assert base_score(rec) == 7.5


def test_base_score_is_none_not_zero_when_nothing_is_scored() -> None:
    """Kode lama: `cna.metrics` ada tapi kosong -> skor "0" (kategori 'None')."""
    assert base_score(record(cna_metrics=[])) is None
    assert base_score(record()) is None
    assert summarize("cve-1", record(), []).score_text == "N/A"


AFFECTED = [{"vendor": "Acme", "product": "Widget", "versions": [{"status": "affected"}]}]


def test_product_and_vendor_come_from_cna_and_adp_without_duplicates() -> None:
    affected = {"vendor": "ACME", "versions": [{"status": "affected"}]}
    adp = [{"affected": [{**affected, "product": "widget"}, {**affected, "product": "Gadget"}]}]

    product, vendor = product_vendor(record(cna_affected=AFFECTED, adp=adp))

    assert product == "widget || Gadget"  # "Widget" (cna) tidak dobel dgn "widget" (adp)
    assert vendor == "acme"


def test_unaffected_and_n_a_products_are_ignored_and_empty_is_unknown() -> None:
    rec = record(
        cna_affected=[
            {"vendor": "n/a", "product": "n/a", "versions": [{"status": "affected"}]},
            {"vendor": "Acme", "product": "Old", "versions": [{"status": "unaffected"}]},
        ]
    )

    product, vendor = product_vendor(rec)

    assert product == ""
    assert vendor == "Acme"  # vendor "n/a" ditimpa entri CNA berikutnya (perilaku lama)
    assert product_vendor(record()) == ("Unknown", "Unknown")


def test_a_malformed_record_never_raises() -> None:
    assert product_vendor({"containers": {"cna": {"affected": "bukan-list"}}}) == (
        "Unknown",
        "Unknown",
    )
    assert base_score({}) is None


def test_tech_stack_match_is_a_literal_substring_and_ignores_blank_entries() -> None:
    """`re.search("", x)` selalu cocok -> satu baris kosong menandai SEMUA CVE 'applicable'."""
    assert applicable_to_stack("palo alto networks", ["Palo Alto", ""]) is True
    assert applicable_to_stack("acme", ["", "  "]) is False
    assert applicable_to_stack("c++ inc", ["c++"]) is True  # metakarakter regex tidak bikin error
    assert applicable_to_stack("acme", ["f5"]) is False


def test_summarize_puts_it_together() -> None:
    rec = record(cna_metrics=[metric(9.8)], cna_affected=AFFECTED)

    s = summarize("cve-2026-1", rec, ["acme"])

    assert (s.cve_id, s.base_score, s.category, s.vendor, s.applicable) == (
        "CVE-2026-1", 9.8, "Critical", "Acme", True,
    )  # fmt: skip


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetch_record_returns_none_for_missing_or_unreadable_records() -> None:
    missing = _client(
        lambda r: httpx.Response(
            404, json={"message": "The cve record for the cve id does not exist."}
        )
    )
    garbage = _client(lambda r: httpx.Response(200, content=b"<html>"))
    server_error = _client(lambda r: httpx.Response(500, json={"error": "x"}))
    fine = _client(lambda r: httpx.Response(200, json={"containers": {}}))

    assert fetch_record(missing, "cve-1") is None
    assert fetch_record(garbage, "cve-1") is None
    assert fetch_record(server_error, "cve-1") is None
    assert fetch_record(fine, "cve-1") == {"containers": {}}
