"""`.env.prod.template` (Fase 10.F) -- template siap-pakai buat `.env` produksi.

Beda dari `.env.example` (dev): file ini boleh menyalakan `Settings()` beneran dan menuntun rotasi
secret, jadi kesalahan di sini nyampe ke server produksi, bukan cuma laptop dev. Test ini menangkap:
salah ketik nama key (typo = `extra="forbid"` bikin container gagal start, tapi baru ketahuan pas
deploy tanpa test ini), key level-compose yang nyasar ke sini (`docker/stack.env` semestinya),
placeholder rotasi yang keisi nilai asli tanpa sengaja (secret ketinggalan di git), dan topik
Telegram yang gak sinkron sama kode.
"""

from __future__ import annotations

import fnmatch
import json
import pathlib

import pytest
from cti_core.config import Settings

ROOT = pathlib.Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / ".env.prod.template"

# Key level-compose (docker/stack.env) -- SENGAJA tidak boleh muncul di .env aplikasi
# (pydantic-settings extra="forbid"). Lihat header .env.prod.template dan docker/stack.env.example.
COMPOSE_LEVEL_PREFIXES = (
    "BIND_ADDR",
    "API_PORT",
    "WEB_PORT",
    "POSTGRES_",
    "REDIS_PORT",
    "CTI_TAG",
    "CTI_ENV_FILE",
    "WORKER_CONCURRENCY",
    "BROWSER_WORKER_CONCURRENCY",
    "NLP_WORKER_CONCURRENCY",
    "TRUSTED_PROXY_HOPS",
    "NGINX_",
    "COMPOSE_PROFILES",
    "VAULT_DEV_ROOT_TOKEN",
)


def parse_env_lines(path: pathlib.Path) -> dict[str, str]:
    """Baris `KEY=value` yang AKTIF (bukan `#`-comment). Komentar di ujung baris (`  # ...`) dibuang
    -- tidak ada value asli di file ini yang mengandung `#`."""
    out: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if " #" in value:
            value = value.split(" #", 1)[0]
        out[key] = value.strip()
    return out


def settings_field_paths() -> set[str]:
    """`"AUTH__JWT_SECRET"`, `"TELEGRAM__THREAD_IDS"`, dst -- dari model Settings beneran, bukan
    disalin manual (kalau field baru ditambah di config.py, test ini otomatis ikut)."""
    paths = set()
    for name, field in Settings.model_fields.items():
        nested = getattr(field.annotation, "model_fields", None)
        if nested:
            paths |= {f"{name.upper()}__{sub.upper()}" for sub in nested}
        else:
            paths.add(name.upper())
    return paths


def env_topics(path: pathlib.Path) -> set[str]:
    value = parse_env_lines(path).get("TELEGRAM__THREAD_IDS")
    assert value, f"TELEGRAM__THREAD_IDS tidak ada di {path.name}"
    return set(json.loads(value))


def test_template_is_not_matched_by_any_gitignore_pattern() -> None:
    """Cocokkan langsung ke isi `.gitignore` (bukan `git check-ignore`): checkout CI (`git
    ls-files` + rsync, dipakai simulasi CI proyek ini) gak selalu bawa `.git`, dan `git
    check-ignore` di luar repo gagal `fatal: not a git repository`, bukan `1` yang diharapkan."""
    assert TEMPLATE.is_file()
    patterns = [
        ln.strip()
        for ln in (ROOT / ".gitignore").read_text().splitlines()
        if ln.strip() and not ln.startswith("#")
    ]
    matched = [p for p in patterns if fnmatch.fnmatch(TEMPLATE.name, p.lstrip("/"))]
    assert matched == [], (
        f".env.prod.template ke-gitignore lewat pola {matched} -- gak akan ke-commit"
    )


def test_every_key_is_a_real_settings_field() -> None:
    declared = set(parse_env_lines(TEMPLATE))
    valid = settings_field_paths()

    unknown = declared - valid
    assert unknown == set(), f"key di .env.prod.template bukan field Settings (typo?): {unknown}"


def test_no_compose_level_variable_leaked_into_the_app_env_template() -> None:
    declared = set(parse_env_lines(TEMPLATE))
    leaked = {k for k in declared if k.startswith(COMPOSE_LEVEL_PREFIXES)}
    assert leaked == set(), (
        f"key level-compose nyasar ke .env.prod.template (harusnya di docker/stack.env): {leaked}"
    )


# Baris yang WAJIB kosong (secret asli belum tentu boleh nempel di git) -- diambil dari tiap
# "# [ ] ROTASI ... KEY" di file, jadi nambah baris rotasi baru otomatis ke-cover di sini.
def rotation_marked_keys() -> set[str]:
    keys = set()
    for line in TEMPLATE.read_text().splitlines():
        if "ROTASI" in line and line.strip().startswith("#"):
            keys.update(w.rstrip(".,") for w in line.split() if w.isupper() and "__" in w)
    return keys


def test_rotation_marked_secrets_are_left_blank_not_filled_with_a_real_value() -> None:
    marked = rotation_marked_keys()
    assert marked == {
        "AUTH__JWT_SECRET",
        "AUTH__SESSION_SECRET_KEY",
        "LLM__API_KEY",
        "TELEGRAM__BOT_TOKEN",
        "TELEGRAM__CHAT_ID",
        "GRAPH__CLIENT_SECRET",
        "NVD__API_KEY",
        "GITHUB__TOKEN",
        "TWITTER__API_KEY",
        "X__BEARER_TOKEN",
    }, f"marker rotasi di .env.prod.template berubah -- sinkronkan set ini: {marked}"

    values = parse_env_lines(TEMPLATE)
    non_blank = {k: v for k in marked if (v := values.get(k, "")) != ""}
    assert non_blank == {}, (
        f"key bertanda ROTASI sudah keisi nilai -- pastikan itu bukan secret asli sebelum commit: "
        f"{sorted(non_blank)}"
    )


def test_telegram_topics_match_env_example() -> None:
    assert env_topics(TEMPLATE) == env_topics(ROOT / ".env.example")


def test_settings_loads_from_the_template_as_is(monkeypatch: pytest.MonkeyPatch) -> None:
    """Semua field selain `AUTH__JWT_SECRET`/`AUTH__SESSION_SECRET_KEY` punya default `""` di
    kode (lihat `config.py`) -- string kosong tetap `str` yang valid, jadi template BOLEH belum
    diisi dan tetap lolos di sini. Yang test ini benar-benar buktikan: tidak ada key salah nama/
    tipe (`extra="forbid"` di setiap model nested) dan nilai `GANTI_INI`/JSON/angka yang sudah
    ada di file itu sendiri terparse tanpa error -- bukan versi yang dimodifikasi."""
    for k, v in parse_env_lines(TEMPLATE).items():
        monkeypatch.setenv(k, v)

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.environment == "prod"
    assert settings.worker.report_utc_offset_hours == 7
    assert set(settings.telegram.thread_ids) == env_topics(TEMPLATE)
