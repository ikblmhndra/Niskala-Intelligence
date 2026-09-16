#!/usr/bin/env bash
# Fase 0.1 — Tarik ScraperNewsWeb/static/ dari prod.
#
# INI AKSI PRIORITAS TERTINGGI DI SELURUH PROYEK.
# static/ ke-gitignore dan cuma ada di satu host produksi. Isinya 27 file JS
# yang merupakan SELURUH frontend. Kalau host itu mati sebelum ini dijalanin,
# frontend-nya hilang — dan dia dipakai sebagai spesifikasi perilaku waktu
# nulis ulang ke Next.js.
#
# Transport sengaja bertingkat (rsync -> tar -> scp): host prod ini minimalis
# dan gak dijamin punya rsync. Salvage gak boleh gagal cuma gara-gara tooling.
source "$(dirname "$0")/_common.sh"
need_cmd ssh tar
need_env CTI_PROD_HOST CTI_PROD_WEB

DEST="$REPO_ROOT/legacy/static"
mkdir -p "$DEST"

# Satu koneksi SSH dipakai ulang buat probe + transfer, jadi password cuma
# ditanya sekali (host ini belum pakai key auth).
SSH_CTL="/tmp/cti-salvage-ssh-$$.sock"
SSH_OPTS=(-o ControlMaster=auto -o ControlPath="$SSH_CTL" -o ControlPersist=60)
RSH="ssh -o ControlMaster=auto -o ControlPath=$SSH_CTL -o ControlPersist=60"
cleanup_ssh() { ssh "${SSH_OPTS[@]}" -O exit "$CTI_PROD_HOST" 2>/dev/null || true; }
trap cleanup_ssh EXIT

info "cek tooling di $CTI_PROD_HOST"
REMOTE_TOOLS=$(ssh "${SSH_OPTS[@]}" "$CTI_PROD_HOST" \
  'for c in rsync tar; do command -v $c >/dev/null 2>&1 && echo $c; done' || true)

info "narik $CTI_PROD_HOST:$CTI_PROD_WEB/static/ -> legacy/static/"

if printf '%s\n' "$REMOTE_TOOLS" | grep -qx rsync && command -v rsync >/dev/null 2>&1; then
  # rsync bawaan macOS (openrsync, kompatibel 2.6.9) gak punya --info=progress2.
  if rsync --info=progress2 --version >/dev/null 2>&1; then
    RSYNC_PROGRESS=(--info=progress2)
  else
    RSYNC_PROGRESS=(--progress)
  fi
  info "transport: rsync"
  rsync -az "${RSYNC_PROGRESS[@]}" -e "$RSH" \
    "$CTI_PROD_HOST:$CTI_PROD_WEB/static/" "$DEST/"

elif printf '%s\n' "$REMOTE_TOOLS" | grep -qx tar; then
  warn "prod gak punya rsync — fallback ke tar-over-ssh"
  info "transport: tar | ssh"
  ssh "${SSH_OPTS[@]}" "$CTI_PROD_HOST" "tar -czf - -C '$CTI_PROD_WEB' static" \
    | tar -xzf - -C "$DEST" --strip-components=1

else
  warn "prod gak punya rsync maupun tar — fallback terakhir ke scp"
  info "transport: scp"
  scp -r "${SSH_OPTS[@]}" "$CTI_PROD_HOST:$CTI_PROD_WEB/static/." "$DEST/"
fi

JS_COUNT=$(find "$DEST" -name '*.js' -type f | wc -l | tr -d ' ')
ALL_COUNT=$(find "$DEST" -type f | wc -l | tr -d ' ')
ok "$JS_COUNT file .js, $ALL_COUNT file total"

if [ "$JS_COUNT" -lt 20 ]; then
  warn "diharapkan ~27 file .js, dapet $JS_COUNT — cek path $CTI_PROD_WEB/static bener apa gak"
fi

cat <<TXT

Langkah berikutnya — LANGSUNG COMMIT, jangan nunggu fase ini kelar:

  git -C "$REPO_ROOT" add legacy/static
  git -C "$REPO_ROOT" commit -m "salvage: recover gitignored frontend static/ from prod"

TXT
