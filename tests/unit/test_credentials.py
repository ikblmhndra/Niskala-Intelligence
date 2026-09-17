"""cti_scraper.credentials -- header auth per-scraper, disuntik Runner
SEBELUM fetch() dipanggil, scraper sendiri gak pernah pegang token mentah."""

import pytest
from cti_core.config import Settings
from cti_scraper.base import ConfigError
from cti_scraper.credentials import resolve_credential_headers

VALID_ENV = {
    "DATABASE__URL": "postgresql+asyncpg://cti:cti@localhost/cti",
    "DATABASE__SYNC_URL": "postgresql+psycopg://cti:cti@localhost/cti",
    "AUTH__JWT_SECRET": "test-secret",
    "AUTH__SESSION_SECRET_KEY": "test-session",
}


def _settings(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> Settings:
    monkeypatch.delenv("SECRETS_BACKEND", raising=False)
    for k, v in {**VALID_ENV, **overrides}.items():
        monkeypatch.setenv(k, v)
    return Settings(_env_file=None)  # type: ignore[call-arg]


def test_github_header(monkeypatch: pytest.MonkeyPatch) -> None:
    s = _settings(monkeypatch, GITHUB__TOKEN="ghp_test123")
    assert resolve_credential_headers("github", settings=s) == {
        "Authorization": "Bearer ghp_test123"
    }


def test_nvd_header(monkeypatch: pytest.MonkeyPatch) -> None:
    s = _settings(monkeypatch, **{"NVD__API_KEY": "nvd-test-key"})
    assert resolve_credential_headers("nvd", settings=s) == {"apiKey": "nvd-test-key"}


def test_twitter_header(monkeypatch: pytest.MonkeyPatch) -> None:
    s = _settings(monkeypatch, **{"TWITTER__API_KEY": "tw-test-key"})
    assert resolve_credential_headers("twitter", settings=s) == {"X-API-Key": "tw-test-key"}


def test_unknown_credential_name_fails_loud(monkeypatch: pytest.MonkeyPatch) -> None:
    s = _settings(monkeypatch)
    with pytest.raises(ConfigError, match="gak dikenal"):
        resolve_credential_headers("bitbucket", settings=s)


def test_empty_secret_fails_loud_not_silent_unauth_request(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression yang mau dicegah: newCveThreat.py lama gak pernah beneran
    kirim apiKey walau field-nya ada di config -- token kosong harus
    ke-tangkep di sini, bukan diam-diam kirim request tanpa auth."""
    s = _settings(monkeypatch)  # github/nvd/twitter sengaja gak di-set
    with pytest.raises(ConfigError, match="kosong"):
        resolve_credential_headers("github", settings=s)
