"""Unit test fungsi murni `cti_api.services.cve_email`. Fase 7.4 Grup C.
`_render_email` dites di sini juga (baca template file asli, gak ada
DB/network -- Jinja2 render doang)."""

from __future__ import annotations

from cti_api.services import cve_email as svc


def test_highest_severity_picks_critical_over_others() -> None:
    cves = [{"severity": "LOW"}, {"severity": "CRITICAL"}, {"severity": "HIGH"}]
    assert svc._highest_severity(cves) == "CRITICAL"


def test_highest_severity_case_insensitive() -> None:
    cves = [{"severity": "high"}]
    assert svc._highest_severity(cves) == "HIGH"


def test_highest_severity_defaults_to_low_when_unrecognized() -> None:
    assert svc._highest_severity([{"severity": "UNKNOWN"}]) == "LOW"


def test_highest_severity_empty_list_defaults_to_low() -> None:
    assert svc._highest_severity([]) == "LOW"


def test_render_email_produces_html_with_expected_content() -> None:
    context = {
        "cve_count": 1,
        "product_name": "Wordpress",
        "due_date": "October 01, 2026",
        "plan_date": "September 26, 2026",
        "email_date": "September 23, 2026",
        "highest_severity": "CRITICAL",
        "remediation_days": 7,
        "cves": [{"id": "CVE-2026-0001", "severity": "CRITICAL", "impact": "RCE"}],
        "risk_context": "<strong>High risk</strong>",
        "remediation_fixes": [{"version_branch": "< 6.5", "fixed_version": "6.5"}],
        "mitigations": ["Enable WAF"],
        "vendor_advisory_url": ["https://example.com/advisory"],
        "timeline_actions": [
            {"description": "Detect", "owner": "CTI", "due_date": "Sep 23, 2026", "critical": False}
        ],
        "tracking_id": "CTI-2026-09-001",
        "classification": "Internal - Confidential",
    }
    html = svc._render_email(context)
    assert "CVE-2026-0001" in html
    assert "CTI-2026-09-001" in html
    assert "High risk" in html
