"""Unit test fungsi murni `cti_api.services.cve_lookup`. Fase 7.4 Grup B
(survei 2026-09-19). Gak butuh DB/network."""

from __future__ import annotations

from cti_api.services import cve_lookup as svc


def test_extract_title_new_list_shape() -> None:
    """API exploit-db beneran balikin `description` sebagai list
    `[edb_id, title]` sekarang (ketauan live-test 2026-09-23) -- bukan
    string kayak yang diasumsikan kode lama."""
    assert svc._extract_title(["50590", "Apache Log4j2 2.14.1 - Info Disclosure"]) == (
        "Apache Log4j2 2.14.1 - Info Disclosure"
    )


def test_extract_title_legacy_plain_string_still_supported() -> None:
    assert svc._extract_title("Some Exploit Title") == "Some Exploit Title"


def test_extract_title_missing_or_malformed() -> None:
    assert svc._extract_title(None) == ""
    assert svc._extract_title("") == ""
    assert svc._extract_title(["50590"]) == ""  # list tanpa elemen title
    assert svc._extract_title([]) == ""


def test_strip_cve_prefix() -> None:
    assert svc._strip_cve_prefix("CVE-2021-44228") == "2021-44228"
    assert svc._strip_cve_prefix("cve-2021-44228") == "2021-44228"
