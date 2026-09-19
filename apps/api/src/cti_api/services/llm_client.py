"""Konstruksi client OpenAI-compatible dipakai bersama di `cti_api`
(`ta_profile.py`, `newsletter.py`) -- duplikat SEMPIT (~15 baris) dari
`cti_enrich.llm.client.get_llm_client()`, BUKAN reuse langsung.

`apps/api` punya exit criteria eksplisit (Fase 7, docs/PROGRESS.md):
"gak ada import `cti_scraper`/`cti_enrich` dari API". `LlmSettings`/
`get_settings()` (sumber config-nya) TETAP dari `cti_core` -- cuma
pembungkus `OpenAI(**kwargs)`-nya yang diulang, disatukan di sini SEKALI
biar dua caller (`ta_profile`/`newsletter`) gak masing-masing duplikat
sendiri-sendiri."""

from __future__ import annotations

from typing import Any

from cti_core.config import LlmSettings, get_settings
from openai import OpenAI


def get_llm_client(settings: LlmSettings | None = None) -> tuple[OpenAI, str]:
    settings = settings or get_settings().llm
    kwargs: dict[str, Any] = {
        "api_key": settings.api_key,
        "timeout": settings.timeout_s,
        "max_retries": settings.max_retries,
    }
    if settings.url:
        kwargs["base_url"] = settings.url
    return OpenAI(**kwargs), settings.model
