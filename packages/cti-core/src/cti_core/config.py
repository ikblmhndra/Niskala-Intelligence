"""Satu sumber config buat seluruh platform. Lihat .env.example di root repo
untuk daftar lengkap key -- file ini HARUS tetap sinkron 1:1 sama file itu;
kalau nambah field di sini, `.env.example` ikut di-update di commit yang sama.

Kenapa `extra="forbid"`: env var yang salah ketik (mis. TELEGRAM__BOTTOKEN)
harus bikin container GAGAL START, bukan diam-diam mati kayak yang kejadian
di app lama (lihat plan §7.1). Pydantic-settings ngasih ini gratis lewat
validasi schema -- gak perlu manual RuntimeError check kayak
`ScraperNewsWeb/app/main.py` lakuin buat SESSION_SECRET_KEY/JWT_SECRET.

Skema secret sekarang vs nanti (docs/SECRETS_ROTATION.md):
  SECRETS_BACKEND=env   (default, sekarang) -- .env satu-satunya sumber.
  SECRETS_BACKEND=vault (produksi)          -- integrasi baca Vault BELUM
                                               diimplementasikan di sini,
                                               disengaja (dikerjain di fase
                                               testing). `vault_token` cuma
                                               divalidasi WAJIB ADA kalau
                                               backend ini dipilih, gak lebih.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class _StrictModel(BaseModel):
    """Base buat semua grup settings nested.

    `extra="forbid"` di `Settings` (BaseSettings) TIDAK otomatis nurun ke
    model nested biasa -- kebukti waktu testing: `TELEGRAM__BOTTOKEN` (typo)
    kepetakan ke field `telegram` yang valid, terus sub-key `bottoken`-nya
    diam-diam ke-drop sama `TelegramSettings` karena BaseModel polos default
    permisif. Persis mode kegagalan "salah ketik = diam-diam mati" yang mau
    dicegah field ini. Tiap grup nested WAJIB inherit dari sini, bukan
    BaseModel langsung.
    """

    model_config = ConfigDict(extra="forbid")


class DatabaseSettings(_StrictModel):
    url: str
    """postgresql+asyncpg://... -- dipakai FastAPI (async session)."""
    sync_url: str
    """postgresql+psycopg://... -- dipakai Celery/CLI (sync session).
    Sama database, driver beda; lihat db/engine.py buat alasannya."""
    pool_size: int = 20
    max_overflow: int = 10


class RedisSettings(_StrictModel):
    url: str = "redis://localhost:6379/0"


class AuthSettings(_StrictModel):
    jwt_secret: str
    """WAJIB ADA, gak ada default. Kosong di .env = container gagal start
    saat Settings() dibikin -- pengganti RuntimeError manual di app lama."""
    jwt_algorithm: str = "HS256"
    jwt_expire_min: int = 480
    session_secret_key: str
    """WAJIB ADA, alasan sama kayak jwt_secret."""


class OidcSettings(_StrictModel):
    enabled: bool = False
    client_id: str = ""
    client_secret: str = ""
    discovery_url: str = ""
    redirect_uri: str = ""


class LlmSettings(_StrictModel):
    provider: Literal["openai", "deepseek", "gemini"] = "openai"
    api_key: str = ""
    url: str = ""
    """Override `base_url` client OpenAI-compatible -- kosong = endpoint
    default provider. Dipakai dev buat nunjuk ke gateway lokal (mis. 9router)
    alih-alih API provider asli."""
    model: str = "gpt-4o"
    timeout_s: float = 60.0
    max_retries: int = 2
    rate_limit: str = "60/minute"
    """Throttle spend global lewat token bucket Redis -- sengaja belum ada
    di app lama (lihat plan §6.4: LLM client web gak punya timeout sama
    sekali, ini yang bikin field ini ada)."""


class TelegramSettings(_StrictModel):
    bot_token: str = ""
    chat_id: str = ""
    thread_ids: dict[str, int] = Field(default_factory=dict)
    """Satu dict, bukan 17 field thread_id_* terpisah kayak config.yml lama.
    Menggantikan 14 fungsi send_alert_* yang masing-masing hardcode satu
    thread (lihat plan §6.5)."""


class GraphSettings(_StrictModel):
    """Microsoft Graph -- pengiriman email CVE notification."""

    tenant_id: str = ""
    client_id: str = ""
    client_secret: str = ""
    sender: str = ""
    cc: str = ""
    """Dulunya hardcoded di ScraperNewsWeb/app/config.py:59-60."""


class NvdSettings(_StrictModel):
    api_key: str = ""


class GithubSettings(_StrictModel):
    token: str = ""


class TwitterSettings(_StrictModel):
    api_key: str = ""


class OtxSettings(_StrictModel):
    api_key: str = ""


class ScraperSettings(_StrictModel):
    default_rate_limit: str = "20/minute"
    default_timeout_s: float = 30.0
    dedup_ttl_days: int = 180
    cold_start_max_items: int = 5
    """Run pertama scraper baru dibatasi segini item. Tanpa ini, DB kosong +
    ~91 scraper aktif = seluruh isi feed masuk sekaligus di hari pertama
    (lihat plan, konsekuensi "Postgres + DB kosong")."""
    enrich_queue_max_depth: int = 2000
    """Guard backpressure -- scraper bisa jauh lebih cepat dari enrichment
    (spaCy/LLM). Lihat plan §4.7."""


class WorkerSettings(_StrictModel):
    """Interval buat 2 dari 5 loop Celery beat (Fase 7.8) yang nentuin
    LOGIKA task, bukan cuma jadwal cron-nya -- IOC decay/daily recap/CVE
    enrichment jam tetap (04:00/06:00/tiap 3 jam UTC, port apa adanya dari
    `_seconds_until_04h_utc()` dkk lama) di-hardcode langsung di `beat.py`,
    gak butuh entri di sini."""

    pir_p1_alert_interval_min: int = 5
    """Port `PIR_P1_INTERVAL_MIN` lama -- P1 dicek tiap segini menit."""
    pir_alert_interval_min: int = 15
    """Port `PIR_ALERT_INTERVAL_MIN` lama -- P2+ dicek tiap segini menit."""
    attack_sync_interval_days: int = 7
    """Port `ATTACK_SYNC_INTERVAL_DAYS` lama -- re-sync kalau domain
    manapun belum pernah sync ATAU sync terlama udah lebih dari ini."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        extra="forbid",
        case_sensitive=False,
    )

    service_name: str = "cti"
    environment: Literal["dev", "staging", "prod"] = "dev"
    log_level: str = "INFO"

    secrets_backend: Literal["env", "vault"] = "env"
    vault_addr: str = "http://vault:8200"
    vault_token: str = ""

    database: DatabaseSettings
    redis: RedisSettings = Field(default_factory=RedisSettings)
    auth: AuthSettings
    oidc: OidcSettings = Field(default_factory=OidcSettings)
    llm: LlmSettings = Field(default_factory=LlmSettings)
    telegram: TelegramSettings = Field(default_factory=TelegramSettings)
    graph: GraphSettings = Field(default_factory=GraphSettings)
    nvd: NvdSettings = Field(default_factory=NvdSettings)
    github: GithubSettings = Field(default_factory=GithubSettings)
    twitter: TwitterSettings = Field(default_factory=TwitterSettings)
    otx: OtxSettings = Field(default_factory=OtxSettings)
    scraper: ScraperSettings = Field(default_factory=ScraperSettings)
    worker: WorkerSettings = Field(default_factory=WorkerSettings)

    cors_origins: str = "http://localhost:3000"
    api_base_url: str = "http://api:8000"

    @model_validator(mode="after")
    def _vault_token_required_when_selected(self) -> Settings:
        if self.secrets_backend == "vault" and not self.vault_token:
            raise ValueError(
                "SECRETS_BACKEND=vault tapi VAULT_TOKEN kosong. "
                "cti_core belum baca secret lain dari Vault (disengaja, "
                "lihat docs/SECRETS_ROTATION.md) -- tapi kalau backend ini "
                "dipilih, token minimal harus ada."
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Satu instance per proses. Testing: pakai `Settings(_env_file=None, **overrides)`
    langsung, jangan panggil fungsi ini (cache-nya lintas-test kalau dipanggil)."""
    return Settings()  # type: ignore[call-arg]  # nilai datang dari env/.env
