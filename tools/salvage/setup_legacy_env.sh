#!/usr/bin/env bash
# Fase 0.5 prasyarat — venv buat ngerekam fixture.
#
# Perekam fixture ngejalanin script scraper LAMA, jadi butuh dependency
# fetch/parse mereka. Tapi TIDAK butuh stack NLP (spacy/sumy) karena
# modules.nlp di-stub — jadi env-nya jauh lebih ringan dari requirements.txt
# aslinya, dan jauh lebih cepat dipasang.
source "$(dirname "$0")/_common.sh"
need_cmd uv

VENV="$REPO_ROOT/.venv-legacy"

info "bikin venv perekam di .venv-legacy"
uv venv --python 3.12 "$VENV" --quiet

# Cuma yang dibutuhin buat fetch + parse. Sengaja TIDAK dipasang:
#   spacy sumy torch bert-extractive-summarizer  -> modules.nlp di-stub
#   python-telegram-bot                          -> modules.* di-stub
# pymongo TETAP dipasang: sebagian script ngimport pymongo langsung, bukan
# lewat modules.dbMongo, jadi stub gak nolongin. Ringan, gak nyambung ke mana2.
#   torch / bert-extractive-summarizer           -> terbukti 0 importer (Fase 0.9)
info "pasang dependency fetch/parse"
VIRTUAL_ENV="$VENV" uv pip install --quiet \
  requests defusedxml lxml lxml_html_clean beautifulsoup4 \
  xmltodict feedparser python-dateutil cpe deep-translator \
  pymongo \
  playwright

info "pasang Chromium buat scraper Playwright (~45 file)"
VIRTUAL_ENV="$VENV" "$VENV/bin/playwright" install chromium --with-deps 2>/dev/null \
  || VIRTUAL_ENV="$VENV" "$VENV/bin/playwright" install chromium

ok "siap: $VENV"

cat <<TXT

Jalanin perekam pakai interpreter ini:

  $VENV/bin/python tools/salvage/record_fixtures.py \\
      --scrapers-dir ../ScraperNews \\
      --out tests/fixtures

TXT
