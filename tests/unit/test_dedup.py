"""Unit test `cti_api.services.dedup.find_dedup_groups` (murni, gak
butuh DB). Fase 7.4 Grup D."""

from __future__ import annotations

from cti_api.services.dedup import find_dedup_groups


def test_single_article_returns_singleton() -> None:
    articles = [{"title": "Apt41 breach", "source": "a", "url": "https://a.com"}]
    result = find_dedup_groups(articles)
    assert len(result) == 1
    assert result[0]["_dup_count"] == 1
    assert result[0]["_dup_sources"] == []
    assert result[0]["_dup_urls"] == []


def test_near_identical_titles_grouped() -> None:
    articles = [
        {"title": "Apt41 hits manufacturing sector hard", "source": "a", "url": "https://a.com"},
        {"title": "Apt41 hits manufacturing sector hard!", "source": "b", "url": "https://b.com"},
    ]
    result = find_dedup_groups(articles, threshold=0.5)
    assert len(result) == 1
    canonical = result[0]
    assert canonical["_dup_count"] == 2
    assert canonical["_dup_sources"] == ["b"]
    assert canonical["_dup_urls"] == ["https://b.com"]
    # kanonik = artikel PERTAMA (caller wajib sort desc posted_on duluan)
    assert canonical["source"] == "a"


def test_distinct_titles_not_grouped() -> None:
    articles = [
        {"title": "Ransomware hits hospital in Jakarta", "source": "a", "url": "https://a.com"},
        {"title": "Zero-day exploited in Chrome browser", "source": "b", "url": "https://b.com"},
    ]
    result = find_dedup_groups(articles, threshold=0.75)
    assert len(result) == 2
    assert all(a["_dup_count"] == 1 for a in result)


def test_empty_titles_returned_as_singletons() -> None:
    articles = [
        {"title": "", "source": "a", "url": "https://a.com"},
        {"title": "   ", "source": "b", "url": "https://b.com"},
    ]
    result = find_dedup_groups(articles)
    assert len(result) == 2
    assert all(a["_dup_count"] == 1 for a in result)


def test_mixed_valid_and_empty_titles() -> None:
    articles = [
        {"title": "Apt41 hits manufacturing", "source": "a", "url": "https://a.com"},
        {"title": "", "source": "b", "url": "https://b.com"},
    ]
    result = find_dedup_groups(articles)
    # cuma 1 artikel dengan judul valid -- gak cukup buat dibandingin,
    # semua balik apa adanya
    assert len(result) == 2
    assert all(a["_dup_count"] == 1 for a in result)


def test_empty_list_returns_empty() -> None:
    assert find_dedup_groups([]) == []


def test_three_way_group_transitive_via_union_find() -> None:
    articles = [
        {"title": "Critical zero-day found in widely used library", "source": "a", "url": "u1"},
        {
            "title": "Critical zero-day found in widely used library today",
            "source": "b",
            "url": "u2",
        },
        {"title": "Critical zero-day found in widely used library now", "source": "c", "url": "u3"},
    ]
    result = find_dedup_groups(articles, threshold=0.5)
    assert len(result) == 1
    assert result[0]["_dup_count"] == 3
