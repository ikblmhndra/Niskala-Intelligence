"""Password hash (bcrypt) + JWT encode/decode -- port 1:1 dari
`ScraperNewsWeb/app/services/auth_service.py` (bagian yang gak nyentuh DB).
Secret/algorithm/expiry dibaca dari `cti_core.config.Settings.auth` (Fase
2), bukan `os.getenv()` langsung kayak app lama -- container gagal start
kalau `JWT_SECRET`/`SESSION_SECRET_KEY` kosong (lihat docstring config.py),
gantiin `RuntimeError` manual yang dulu ada di `main.py:lifespan()`."""

from __future__ import annotations

import datetime
from typing import Any

import bcrypt
from cti_core.config import get_settings
from jose import jwt


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_token(username: str, role: str, client_ids: list[str] | None = None) -> str:
    settings = get_settings().auth
    expire = datetime.datetime.now(datetime.UTC) + datetime.timedelta(
        minutes=settings.jwt_expire_min
    )
    return str(
        jwt.encode(
            {
                "sub": username,
                "role": role,
                "client_ids": client_ids or ["default"],
                "exp": expire,
            },
            settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
        )
    )


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings().auth
    result: dict[str, Any] = jwt.decode(
        token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
    )
    return result
