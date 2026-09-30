"""`cti_scraper.options` -- opsi per-scraper yang bisa diubah dari control plane."""

from __future__ import annotations

import pytest
from cti_scraper.base import OptionChoice, ScraperMeta, ScraperOption
from cti_scraper.options import OptionError, credential_for, resolve_options, validate_options

PROVIDER = ScraperOption(
    key="provider",
    label="Sumber",
    choices=(
        OptionChoice("a", "A", credential="cred-a"),
        OptionChoice("b", "B", credential="cred-b"),
        OptionChoice("c", "C"),  # tanpa kredensial sendiri
    ),
    default="a",
)


def meta(*options: ScraperOption, credential: str | None = "meta-cred") -> ScraperMeta:
    return ScraperMeta(
        id="x", source="X", schedule="* * * * *", options=options, credential=credential
    )


# --- resolve_options ----------------------------------------------------------------


def test_no_declared_options_means_no_effective_options() -> None:
    assert resolve_options(meta(), {"provider": "b"}) == {}


def test_default_applies_when_nothing_is_chosen() -> None:
    assert resolve_options(meta(PROVIDER)) == {"provider": "a"}
    assert resolve_options(meta(PROVIDER), {}) == {"provider": "a"}


def test_admin_choice_beats_default_and_cli_override_beats_admin_choice() -> None:
    m = meta(PROVIDER)

    assert resolve_options(m, {"provider": "b"}) == {"provider": "b"}
    assert resolve_options(m, {"provider": "b"}, {"provider": "c"}) == {"provider": "c"}


def test_stored_garbage_is_ignored_so_the_scraper_keeps_running_on_the_default() -> None:
    """Pilihan bisa dihapus dari kode setelah admin sempat memilihnya: JANGAN mati tiap jadwal."""
    m = meta(PROVIDER)

    assert resolve_options(m, {"provider": "sudah-dihapus"}) == {"provider": "a"}
    assert resolve_options(m, {"opsi-hantu": "b"}) == {"provider": "a"}


def test_a_bad_cli_override_is_rejected_not_ignored() -> None:
    """Beda dari data tersimpan: override CLI itu input operator langsung -- typo harus keras."""
    with pytest.raises(OptionError, match="tidak boleh 'z'"):
        resolve_options(meta(PROVIDER), None, {"provider": "z"})


# --- validate_options ---------------------------------------------------------------


def test_validate_accepts_declared_choices_and_returns_a_copy() -> None:
    values = {"provider": "b"}

    out = validate_options(meta(PROVIDER), values)

    assert out == values and out is not values


def test_validate_rejects_unknown_key_and_value_with_the_valid_alternatives() -> None:
    with pytest.raises(OptionError, match=r"tidak punya opsi 'nope'.*provider"):
        validate_options(meta(PROVIDER), {"nope": "a"})
    with pytest.raises(OptionError, match=r"\['a', 'b', 'c'\]"):
        validate_options(meta(PROVIDER), {"provider": "z"})
    with pytest.raises(OptionError, match="tidak punya opsi"):
        validate_options(meta(), {"provider": "a"})  # scraper tanpa opsi apa pun


# --- credential_for -----------------------------------------------------------------


def test_the_chosen_option_decides_the_credential() -> None:
    m = meta(PROVIDER)

    assert credential_for(m, {"provider": "a"}) == "cred-a"
    assert credential_for(m, {"provider": "b"}) == "cred-b"


def test_a_choice_without_its_own_credential_falls_back_to_the_meta_credential() -> None:
    assert credential_for(meta(PROVIDER), {"provider": "c"}) == "meta-cred"
    assert credential_for(meta(), {}) == "meta-cred"
    assert credential_for(meta(credential=None), {}) is None
