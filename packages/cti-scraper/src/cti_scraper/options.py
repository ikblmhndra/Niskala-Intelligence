"""Opsi per-scraper yang bisa diubah dari control plane (`ScraperMeta.options`).

Tiga fungsi murni, tanpa I/O:

  - `resolve_options` -- nilai EFEKTIF buat `Runner`: default kode, ditimpa pilihan
    admin (`ScraperConfig.options`), ditimpa override eksplisit (CLI `--option`).
    TOLERAN: key/nilai yang tidak dikenal di data tersimpan DIABAIKAN (bukan error)
    -- pilihan bisa dihapus dari kode setelah admin sempat memilihnya; scraper harus
    tetap jalan pakai default, bukan mati tiap jadwal.
  - `validate_options` -- gerbang API (PUT config) dan CLI: STRICT, key/nilai yang
    salah = `OptionError`. Data buruk ditolak di depan, bukan ditelan diam-diam nanti.
  - `credential_for` -- kredensial yang harus dipasang `Runner`: milik pilihan aktif
    kalau ada, else `ScraperMeta.credential`.
"""

from __future__ import annotations

from collections.abc import Mapping

from cti_scraper.base import ScraperMeta


class OptionError(ValueError):
    """Opsi yang dikirim tidak cocok dengan yang dideklarasikan scraper."""


def resolve_options(
    meta: ScraperMeta,
    chosen: Mapping[str, str] | None = None,
    overrides: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """`{key: value}` efektif untuk SEMUA opsi yang dideklarasikan `meta` (kosong kalau
    tidak ada). Urutan: default < `chosen` (DB) < `overrides` (CLI). Yang tidak valid
    di `chosen` diabaikan; di `overrides` -> `OptionError` (itu input operator langsung)."""
    if overrides:
        validate_options(meta, overrides)
    effective: dict[str, str] = {}
    for option in meta.options:
        allowed = {c.value for c in option.choices}
        value = option.default
        for source in (chosen, overrides):
            if source and source.get(option.key) in allowed:
                value = source[option.key]
        effective[option.key] = value
    return effective


def validate_options(meta: ScraperMeta, values: Mapping[str, str]) -> dict[str, str]:
    """Kembalikan salinan `values` kalau semuanya valid; kalau tidak `OptionError`."""
    declared = {o.key: o for o in meta.options}
    for key, value in values.items():
        option = declared.get(key)
        if option is None:
            known = sorted(declared) or "tidak ada"
            raise OptionError(f"scraper '{meta.id}' tidak punya opsi '{key}' (yang ada: {known})")
        allowed = [c.value for c in option.choices]
        if value not in allowed:
            raise OptionError(f"opsi '{key}' tidak boleh '{value}' -- pilihan: {allowed}")
    return dict(values)


def credential_for(meta: ScraperMeta, options: Mapping[str, str]) -> str | None:
    """Nama kredensial untuk run ini. Pilihan aktif yang mendeklarasikan `credential`
    menang atas `ScraperMeta.credential`."""
    for option in meta.options:
        for choice in option.choices:
            if choice.value == options.get(option.key) and choice.credential is not None:
                return choice.credential
    return meta.credential
