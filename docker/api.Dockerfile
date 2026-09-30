# syntax=docker/dockerfile:1.7
#
# Image `api` (FastAPI) -- plan §10. Context = ROOT repo:
#   docker build -f docker/api.Dockerfile -t cti-api .
#
# Yang SENGAJA gak ada di sini: spaCy/sumy/nltk (itu `worker-nlp`, lihat
# docker/worker.Dockerfile). API cuma bawa `cti-api` + dependency-nya.
#
# Chromium ADA (`playwright install`) karena `cti_api.services.newsletter.
# fetch_article_body` pakai Playwright buat ngambil body artikel (deteksi
# paywall). ~600MB, bukan multi-GB -- beda kelas dari torch yang dibuang di
# Fase 10.A.

ARG PYTHON_IMAGE=python:3.12-slim-bookworm
ARG UV_VERSION=0.12.6

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

# ---------------------------------------------------------------- builder --
FROM ${PYTHON_IMAGE} AS builder
COPY --from=uv /uv /bin/uv
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app

# Layer 1 -- cuma manifest: dependency pihak ketiga ke-cache selama
# pyproject/uv.lock gak berubah (source berubah tiap commit, dependency enggak).
# Semua member workspace HARUS ada pyproject-nya biar `uv` bisa nyusun graph
# (walau `--package cti-api` cuma nginstall sebagian).
COPY pyproject.toml uv.lock .python-version ./
COPY packages/cti-core/pyproject.toml packages/cti-core/pyproject.toml
COPY packages/cti-scraper/pyproject.toml packages/cti-scraper/pyproject.toml
COPY packages/cti-enrich/pyproject.toml packages/cti-enrich/pyproject.toml
COPY packages/cti-alerts/pyproject.toml packages/cti-alerts/pyproject.toml
COPY scrapers/pyproject.toml scrapers/pyproject.toml
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY apps/worker/pyproject.toml apps/worker/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-workspace --package cti-api

# Layer 2 -- source, install member workspace NON-editable (venv mandiri,
# gak nunjuk ke /app/packages/... yang gak ikut ke image runtime).
COPY packages packages
COPY scrapers scrapers
COPY apps/api apps/api
COPY apps/worker apps/worker
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable --package cti-api

# ------------------------------------------------------------ browser-base --
# Python slim + Chromium + library sistemnya (~600MB, ~2 menit) -- stage
# TERPISAH dari venv, jadi layer-nya GAK ke-invalidate tiap source berubah.
# `playwright==` di-pin lewat ARG dan HARUS sama dengan yang di uv.lock --
# dijaga dua lapis: build GAGAL kalau launch Chromium di stage runtime gagal
# (versi beda = revisi browser beda), dan
# `tests/unit/test_dockerfile_playwright_pin.py` nangkep drift di PR.
# Stage ini sengaja IDENTIK di api.Dockerfile dan worker.Dockerfile, jadi
# layer-nya dishare lewat cache antar-image.
FROM ${PYTHON_IMAGE} AS browser-base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:${PATH}" \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ARG PLAYWRIGHT_VERSION=1.63.0
COPY --from=uv /uv /bin/uv
RUN UV_PYTHON_DOWNLOADS=never uv tool run --from "playwright==${PLAYWRIGHT_VERSION}" \
        playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/* /root/.cache

# ---------------------------------------------------------------- runtime --
FROM browser-base AS runtime
RUN useradd --system --uid 10001 --home-dir /home/cti --create-home cti
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
# Bukti Chromium bener-bener bisa jalan dgn venv INI (versi + library sistem).
RUN python -c "from playwright.sync_api import sync_playwright as sp; p = sp().start(); p.chromium.launch().close(); p.stop()"

# Registry harus penuh -- `discover()` balik kosong DIAM-DIAM kalau paket
# `cti-scrapers` gak ter-install, jadi kita paksa gagal di build.
RUN python -c "from cti_scraper.registry import discover; n = len(discover()); assert n > 50, f'registry cuma {n} scraper'"

# `alembic upgrade head` (service `migrate` di compose) dijalanin dari image
# ini -- alembic.ini + alembic/ HARUS ada di WORKDIR. CHANGELOG.md dicari
# `routers/changelog.py` dengan naik dari lokasi modul (venv ada di /app/.venv,
# jadi /app/CHANGELOG.md ketemu).
COPY alembic.ini CHANGELOG.md ./
COPY alembic alembic

USER cti
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).status == 200 else 1)"

# Di belakang proxy (web Next.js = BFF, di depannya nginx): `--proxy-headers`
# bikin `request.client.host` ngikutin X-Forwarded-For, yang dipakai rate
# limit login + audit log. `--forwarded-allow-ips '*'` AMAN cuma karena port
# API gak pernah di-publish ke luar (compose: 127.0.0.1) -- kalau suatu saat
# API dibuka langsung, ganti ke IP/subnet proxy-nya (header ini bisa dipalsuin).
# Jumlah worker: env WEB_CONCURRENCY (dibaca uvicorn langsung).
ENV WEB_CONCURRENCY=2
CMD ["uvicorn", "cti_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
