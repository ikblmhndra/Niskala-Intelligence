"""Unit test `cti_api.services.cluster_tokenize` (murni, gak butuh DB).
Fase 7.4 Grup A."""

from __future__ import annotations

from cti_api.services import cluster_tokenize as tok


def test_tokenize_for_dedup_drops_stopwords_and_short_tokens() -> None:
    result = tok.tokenize_for_dedup("The Quick Brown Fox and a Dog")
    assert "the" not in result
    assert "and" not in result
    assert "dog" not in result  # len 3, gak lolos > 3
    assert "quick" in result
    assert "brown" in result


def test_tfidf_tokenize_extracts_cve_ids_separately() -> None:
    tokens = tok.tfidf_tokenize("Exploit found for CVE-2024-1234 in WordPress plugin")
    assert "cve-2024-1234" in tokens
    assert "exploit" in tokens
    assert "wordpress" in tokens


def test_jaccard_empty_sets_returns_zero() -> None:
    assert tok.jaccard(frozenset(), frozenset({"a"})) == 0.0
    assert tok.jaccard(frozenset({"a"}), frozenset()) == 0.0


def test_jaccard_identical_sets_returns_one() -> None:
    s = frozenset({"a", "b", "c"})
    assert tok.jaccard(s, s) == 1.0


def test_jaccard_partial_overlap() -> None:
    a = frozenset({"a", "b"})
    b = frozenset({"b", "c"})
    assert tok.jaccard(a, b) == 1 / 3


def test_confidence_label_thresholds() -> None:
    assert tok.confidence_label(5) == "high"
    assert tok.confidence_label(3) == "medium"
    assert tok.confidence_label(2) == "low"
    assert tok.confidence_label(0) == "low"


def test_cluster_id_deterministic_for_same_name() -> None:
    a = tok.cluster_id("Apt41 Targets Manufacturing")
    b = tok.cluster_id("apt41 targets manufacturing")  # case-insensitive
    c = tok.cluster_id("  Apt41   Targets Manufacturing  ")  # whitespace-normalized
    assert a == b == c
    assert len(a) == 16


def test_cluster_id_differs_for_different_names() -> None:
    a = tok.cluster_id("Apt41 Targets Manufacturing")
    b = tok.cluster_id("Lazarus Targets Finance")
    assert a != b


def test_derive_cluster_name_empty_returns_unknown() -> None:
    assert tok.derive_cluster_name([]) == "Unknown Cluster"


def test_derive_cluster_name_single_title_returns_as_is() -> None:
    assert tok.derive_cluster_name(["Apt41 Breaches Manufacturing Firm"]) == (
        "Apt41 Breaches Manufacturing Firm"
    )


def test_derive_cluster_name_extracts_common_words_across_titles() -> None:
    titles = [
        "Apt41 hits manufacturing sector hard today",
        "Apt41 hits manufacturing sector hard again",
        "Apt41 hits manufacturing sector hard once more",
    ]
    name = tok.derive_cluster_name(titles)
    assert "Apt41" in name


def test_derive_cluster_name_entity_tokens_qualify_at_lower_threshold() -> None:
    titles = [
        "CVE-2024-9999 discovered in library",
        "New details on CVE-2024-9999 emerge",
        "Vendor patches CVE-2024-9999 finally",
        "Researchers analyze CVE-2024-9999 exploit",
    ]
    name = tok.derive_cluster_name(titles)
    assert "cve-2024-9999" in name.lower()
