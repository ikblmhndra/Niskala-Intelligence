"""Unit test `cti_api.services.policy.validate_password`/`policy_hint` --
fungsi murni, port 1:1 dari `ScraperNewsWeb/app/services/policy_service.py`."""

from __future__ import annotations

from cti_api.services.policy import policy_hint, validate_password

_DEFAULT_POLICY = {
    "min_length": 8,
    "require_upper": True,
    "require_lower": True,
    "require_number": True,
    "require_symbol": True,
}


def test_valid_password_no_errors() -> None:
    assert validate_password("GoodPassw0rd!", _DEFAULT_POLICY) == []


def test_too_short_flagged() -> None:
    errors = validate_password("Ab1!", _DEFAULT_POLICY)
    assert any("8 characters" in e for e in errors)


def test_missing_uppercase_flagged() -> None:
    errors = validate_password("lowercase1!", _DEFAULT_POLICY)
    assert "uppercase letter" in errors


def test_missing_lowercase_flagged() -> None:
    errors = validate_password("UPPERCASE1!", _DEFAULT_POLICY)
    assert "lowercase letter" in errors


def test_missing_number_flagged() -> None:
    errors = validate_password("NoNumbersHere!", _DEFAULT_POLICY)
    assert "number" in errors


def test_missing_symbol_flagged() -> None:
    errors = validate_password("NoSymbolsHere1", _DEFAULT_POLICY)
    assert "symbol" in errors


def test_relaxed_policy_allows_simple_password() -> None:
    relaxed = {
        "min_length": 4,
        "require_upper": False,
        "require_lower": True,
        "require_number": False,
        "require_symbol": False,
    }
    assert validate_password("plain", relaxed) == []


def test_policy_hint_lists_all_requirements() -> None:
    hint = policy_hint(_DEFAULT_POLICY)
    assert "Min 8 chars" in hint
    assert "uppercase" in hint
    assert "lowercase" in hint
    assert "number" in hint
    assert "symbol" in hint


def test_policy_hint_omits_disabled_requirements() -> None:
    hint = policy_hint({**_DEFAULT_POLICY, "require_symbol": False})
    assert "symbol" not in hint
