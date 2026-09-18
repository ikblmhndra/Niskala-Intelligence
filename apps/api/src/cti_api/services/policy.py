"""Kebijakan kompleksitas password -- port 1:1 dari
`ScraperNewsWeb/app/services/policy_service.py`. `validate_password`/
`policy_hint` fungsi murni (gak nyentuh DB), `get_policy`/`save_policy`
lewat `AsyncPasswordPolicyRepo`."""

from __future__ import annotations

import re
from typing import Any

from cti_core.db.repositories.auth import AsyncPasswordPolicyRepo
from sqlalchemy.ext.asyncio import AsyncSession


async def get_policy(session: AsyncSession) -> dict[str, Any]:
    return await AsyncPasswordPolicyRepo(session).get()


async def save_policy(session: AsyncSession, policy: dict[str, Any]) -> dict[str, Any]:
    result = await AsyncPasswordPolicyRepo(session).save(policy)
    await session.commit()
    return result


def validate_password(password: str, policy: dict[str, Any]) -> list[str]:
    """List pelanggaran. Kosong = valid."""
    errors = []
    min_len = policy.get("min_length", 8)
    if len(password) < min_len:
        errors.append(f"min {min_len} characters")
    if policy.get("require_upper", True) and not re.search(r"[A-Z]", password):
        errors.append("uppercase letter")
    if policy.get("require_lower", True) and not re.search(r"[a-z]", password):
        errors.append("lowercase letter")
    if policy.get("require_number", True) and not re.search(r"[0-9]", password):
        errors.append("number")
    if policy.get("require_symbol", True) and not re.search(r"[^A-Za-z0-9]", password):
        errors.append("symbol")
    return errors


def policy_hint(policy: dict[str, Any]) -> str:
    parts = [f"Min {policy.get('min_length', 8)} chars"]
    if policy.get("require_upper", True):
        parts.append("uppercase")
    if policy.get("require_lower", True):
        parts.append("lowercase")
    if policy.get("require_number", True):
        parts.append("number")
    if policy.get("require_symbol", True):
        parts.append("symbol")
    return " · ".join(parts)
