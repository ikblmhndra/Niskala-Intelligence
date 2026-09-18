"""cti_enrich.routing -- satu test per cabang cascade (plan Fase 5 exit
criteria: "tiap cabang routing ada test"), plus kasus tepi yang jadi alasan
`route()` didesain kayak gini (double alert OT, sub-routing Indonesia,
`related_tech_cve_status` cuma valid di cabang Global)."""

from cti_enrich.routing import RoutingInput, route

_BASE_MSG = (
    "\n    === <b>GBHACKER</b> ===\n"
    "<b>Title</b>: Some Article Title\n"
    "<b>Posted On</b>: 2026-01-01\n"
    '<b>Link</b>: <a href="https://example.com">Read Now</a>\n'
    "<b>Impacted Industries</b>: General\n"
)


def _inp(**overrides) -> RoutingInput:
    defaults = dict(
        msg_data_base=_BASE_MSG,
        industries_impacted=["General"],
        mentioned_group=[],
        mentioned_countries=[],
        mentioned_apac_people=[],
        cve_list_title=[],
        report_status=False,
        ot_status=False,
        related_tech_status=False,
        related_tech_cve_status=False,
        databreach_list=[],
        zero_day_list=[],
        ttp_string="",
    )
    defaults.update(overrides)
    return RoutingInput(**defaults)


def test_global_article_no_mentions_routes_global() -> None:
    result = route(_inp())
    assert result.news_type == "global"
    assert result.alert_topics == ["global"]
    assert result.threat_actors == []


def test_regional_and_ta_group_article() -> None:
    """`news_type` tetap "apac" (literal) -- sub-routing "apac_indo" cuma
    ngaruh ke alert_topics (channel Telegram), bukan nilai yang dipersist."""
    result = route(_inp(mentioned_group=["APT41"], mentioned_countries=["Indonesia"]))
    assert result.news_type == "apac"
    assert result.alert_topics == ["apac_indo"]
    assert result.threat_actors == ["Apt41"]
    assert "Related Threat Actor" in result.msg_data
    assert "Mentioned Country/People" in result.msg_data


def test_regional_article_only_country() -> None:
    result = route(_inp(mentioned_countries=["Japan"]))
    assert result.news_type == "apac"
    assert result.alert_topics == ["apac"]
    assert result.threat_actors == []
    assert result.mentioned_countries == ["Japan"]


def test_ta_group_article_routes_apt() -> None:
    """Kuirk asli: `news_type` yang dipersist tetap literal "global" (param
    yang diteruskan ke `_sendAlert` di cabang ini) -- CUMA alert_topics yang
    ke channel APT. Article "Global" (A) dan "TA Group" (D) dua-duanya
    persist "global" saat jatuh ke fallback ini, walau beda channel Telegram."""
    result = route(_inp(mentioned_group=["Lazarus"]))
    assert result.news_type == "global"
    assert result.alert_topics == ["apt"]
    assert result.threat_actors == ["Lazarus"]
    assert "Mentioned Country/People" not in result.msg_data


def test_zero_day_takes_priority_over_everything() -> None:
    result = route(_inp(zero_day_list=["zero-day"], report_status=True, ot_status=True))
    assert result.news_type == "Zero Day Article"
    assert result.alert_topics == ["zero_day"]


def test_databreach_routes_before_report_and_ot() -> None:
    result = route(_inp(databreach_list=["data breach"], report_status=True))
    assert result.news_type == "Data Breach Article"
    assert result.alert_topics == ["data_breach"]


def test_databreach_indonesia_submarks_topic() -> None:
    result = route(_inp(databreach_list=["data breach"], mentioned_countries=["Indonesia"]))
    assert result.news_type == "Data Breach Article"
    assert result.alert_topics == ["data_breach_indo"]


def test_report_status_routes_vendor_report() -> None:
    result = route(_inp(report_status=True))
    assert result.news_type == "Vendor Report Article"
    assert result.alert_topics == ["vendor_report"]


def test_ot_status_routes_ot() -> None:
    result = route(_inp(ot_status=True))
    assert result.news_type == "OT Article"
    assert result.alert_topics == ["ot"]


def test_related_tech_status_routes_tech_stack() -> None:
    result = route(_inp(related_tech_status=True))
    assert result.news_type == "Tech Stack Article"
    assert result.alert_topics == ["tech_stack"]


def test_related_tech_cve_status_routes_tech_stack() -> None:
    """`related_tech_cve_status` cuma valid (dihitung) di cabang Global --
    lihat docstring `RoutingInput`. Di sini cuma diuji route() KONSUMSI-nya
    dengan benar, bukan siapa yang menghitungnya."""
    result = route(_inp(related_tech_cve_status=True))
    assert result.news_type == "Tech Stack Article"
    assert result.alert_topics == ["tech_stack"]


def test_unrelated_tech_with_cve_routes_tech_stack_unrelated() -> None:
    result = route(_inp(related_tech_status=False, cve_list_title=["CVE-2026-1234"]))
    assert result.news_type == "Unrelated Tech Stack Article"
    assert result.alert_topics == ["tech_stack_unrelated"]


def test_vuln_keyword_fallback_routes_tech_stack_unrelated() -> None:
    msg = _BASE_MSG.replace("Some Article Title", "Critical flaws enables remote takeover")
    result = route(_inp(msg_data_base=msg))
    assert result.news_type == "Unrelated Tech Stack Article"
    assert result.alert_topics == ["tech_stack_unrelated"]


def test_no_signal_at_all_falls_through_to_generic_global() -> None:
    result = route(_inp())
    assert result.news_type == "global"
    assert result.alert_topics == ["global"]


def test_ot_industry_pre_check_fires_extra_alert_alongside_cascade() -> None:
    """Properti "double alert" asli `_sendAlert` -- OT pre-check (industri
    GPT) TIDAK short-circuit, cascade utama tetap jalan dan bisa pilih topic
    lain. Dua alert_topics, tapi news_type ikut cascade (bukan OT)."""
    result = route(_inp(industries_impacted=["Energy & Utilities"], zero_day_list=["zero-day"]))
    assert result.alert_topics == ["ot", "zero_day"]
    assert result.news_type == "Zero Day Article"


def test_ttp_string_appended_when_present() -> None:
    result = route(_inp(ttp_string="Phishing (T1566)"))
    assert "Related TTP" in result.msg_data
    assert "Phishing (T1566)" in result.msg_data


def test_ttp_string_absent_when_empty() -> None:
    result = route(_inp())
    assert "Related TTP" not in result.msg_data
