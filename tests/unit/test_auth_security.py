"""Unit test `cti_api.security` -- hash password (bcrypt) + JWT
encode/decode. Murni fungsi, gak nyentuh DB/Redis -- `get_settings()`
baca `.env` repo apa adanya (JWT_SECRET dkk udah ada di situ), SENGAJA
gak di-override di sini (lihat `tests/integration/conftest.py`: override
env var global bocor ke test lain kalau gak lewat `monkeypatch`)."""

from __future__ import annotations

import pytest
from cti_api.security import create_token, decode_token, hash_password, verify_password
from jose import JWTError, jwt


def test_hash_password_roundtrip() -> None:
    hashed = hash_password("Sup3rSecr3t!")
    assert hashed != "Sup3rSecr3t!"
    assert verify_password("Sup3rSecr3t!", hashed)


def test_verify_password_rejects_wrong_password() -> None:
    hashed = hash_password("Sup3rSecr3t!")
    assert not verify_password("wrong", hashed)


def test_hash_password_different_salt_each_call() -> None:
    """bcrypt salt acak -- dua hash password sama HARUS beda string,
    kalau sama berarti salt-nya gak jalan (regresi keamanan serius)."""
    h1 = hash_password("same-password")
    h2 = hash_password("same-password")
    assert h1 != h2
    assert verify_password("same-password", h1)
    assert verify_password("same-password", h2)


def test_create_and_decode_token_roundtrip() -> None:
    token = create_token("alice", "analyst", client_ids=["default", "acme"])
    payload = decode_token(token)
    assert payload["sub"] == "alice"
    assert payload["role"] == "analyst"
    assert payload["client_ids"] == ["default", "acme"]


def test_create_token_defaults_client_ids() -> None:
    token = create_token("bob", "admin")
    payload = decode_token(token)
    assert payload["client_ids"] == ["default"]


def test_decode_token_rejects_tampered_token() -> None:
    token = create_token("alice", "analyst")
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    with pytest.raises(JWTError):
        decode_token(tampered)


def test_decode_token_rejects_wrong_secret() -> None:
    from cti_core.config import get_settings

    settings = get_settings().auth
    bad_token = jwt.encode(
        {"sub": "eve", "role": "superadmin"}, "wrong-secret", algorithm=settings.jwt_algorithm
    )
    with pytest.raises(JWTError):
        decode_token(bad_token)
