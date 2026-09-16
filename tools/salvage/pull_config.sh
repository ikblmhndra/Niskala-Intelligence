#!/usr/bin/env bash
# Fase 0.3 — Ambil ScraperNews/config/config.yml dari prod.
#
# Ke-gitignore, jadi gak ada di checkout. Dibutuhin buat mastiin nama DB dan
# collection asli sebelum skema Postgres dirancang.
#
# BERISI KREDENSIAL — ditaruh di legacy/ yang udah masuk .gitignore.
source "$(dirname "$0")/_common.sh"
need_cmd scp
need_env CTI_PROD_HOST CTI_PROD_SCRAPER

DEST="$REPO_ROOT/legacy/config.yml"
mkdir -p "$(dirname "$DEST")"

info "narik config.yml"
scp -q "$CTI_PROD_HOST:$CTI_PROD_SCRAPER/config/config.yml" "$DEST"
chmod 600 "$DEST"
ok "ketulis ke legacy/config.yml (mode 600)"

info "key tingkat atas (nilai tidak ditampilkan):"
grep -E '^[a-zA-Z_]+:' "$DEST" | sed 's/:.*/:/' | sed 's/^/    /'

cat <<TXT

JANGAN DI-COMMIT. Pastikan .gitignore udah punya baris 'legacy/config.yml'.
Verifikasi:  git -C "$REPO_ROOT" check-ignore -v legacy/config.yml

TXT
