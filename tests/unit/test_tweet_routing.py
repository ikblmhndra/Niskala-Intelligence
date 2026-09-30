"""`cti_enrich.tweet_routing.route_tweet` -- port `_sendAlert` tweet (Fase 10.E).

Urutan cascade adalah kontraknya; tiap test mengunci satu anak tangga dan
sekaligus bahwa anak tangga di ATASNYA menang kalau keduanya kena.
"""

from __future__ import annotations

import pytest
from cti_enrich.tweet_routing import TweetRoutingInput, route_tweet


def inp(msg: str = "biasa saja", **over: object) -> TweetRoutingInput:
    base = {
        "msg_data": msg, "news_type": "global", "mentioned_group": [], "cve_list": [],
        "related_tech_status": False, "report_status": False, "ot_status": False,
        "databreach_list": [], "zero_day_list": [],
    }  # fmt: skip
    return TweetRoutingInput(**{**base, **over})  # type: ignore[arg-type]


def test_zero_day_beats_everything() -> None:
    everything = inp(
        "new claim on the shame-site", zero_day_list=["0-day"], databreach_list=["leak"],
        report_status=True, ot_status=True, related_tech_status=True, cve_list=["cve-1"],
    )  # fmt: skip

    assert route_tweet(everything) == ["zero_day"]


def test_data_breach_goes_to_the_indonesian_topic_when_indonesia_is_mentioned() -> None:
    assert route_tweet(inp("kebocoran data", databreach_list=["x"])) == ["data_breach"]
    assert route_tweet(inp("Indonesian firm leaked", databreach_list=["x"])) == ["data_breach_indo"]
    assert route_tweet(inp("bocor 🇮🇩", databreach_list=["x"])) == ["data_breach_indo"]


def test_shame_site_claims_are_dropped_even_though_a_report_flag_is_set() -> None:
    assert route_tweet(inp("New claim on the shame-site", report_status=True)) == []


@pytest.mark.parametrize(
    ("flags", "expected"),
    [
        ({"report_status": True, "ot_status": True}, ["vendor_report"]),
        ({"ot_status": True, "related_tech_status": True}, ["ot"]),
        ({"related_tech_status": True, "cve_list": ["cve-1"]}, ["tech_stack"]),
        ({"cve_list": ["cve-1"]}, ["tech_stack_unrelated"]),
    ],
)
def test_cascade_order_report_then_ot_then_tech_stack_then_unrelated_cve(flags, expected) -> None:
    assert route_tweet(inp(**flags)) == expected


def test_hashtag_and_phrase_rules() -> None:
    assert route_tweet(inp("Fresh #ThreatReport out now")) == ["vendor_report"]
    assert route_tweet(inp("Ransomware Alert: acme")) == []
    assert route_tweet(inp("New hacktivist alliance formed")) == ["global"]
    assert route_tweet(inp("New hacktivist alliance formed", mentioned_group=["apt1"])) == ["apt"]


def test_vulnerability_wording_is_unrelated_tech_stack_and_skips_the_ot_check() -> None:
    msg = "Critical flaw in energy & utilities gear"

    assert route_tweet(inp(msg)) == ["tech_stack_unrelated"]  # tidak juga ke `ot`


def test_ot_keyword_sends_to_ot_and_ALSO_to_the_generic_topic() -> None:
    """Perilaku asli: `send_alert_ot(...)` lalu `send_alert(...)` tetap jalan."""
    assert route_tweet(inp("Attack on critical infrastructure")) == ["ot", "global"]
    assert route_tweet(inp("critical infrastructure", news_type="apac")) == ["ot", "apac"]


@pytest.mark.parametrize(
    ("news_type", "group", "msg", "expected"),
    [
        ("global", [], "halo", "global"),
        ("global", ["apt41"], "halo", "apt"),  # ada grup -> kanal APT
        ("apac", [], "halo", "apac"),
        ("apac", ["apt41"], "halo", "apac"),  # apac menang atas grup
        ("apac", [], "Indonesia diserang", "apac_indo"),
    ],
)
def test_generic_topic_by_news_type_and_group(news_type, group, msg, expected) -> None:
    assert route_tweet(inp(msg, news_type=news_type, mentioned_group=group)) == [expected]
