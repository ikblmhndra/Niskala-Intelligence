#!/usr/bin/env bash
# Fase 0.4 — Dump kedua DB Mongo DAN tes restore-nya.
#
# Karena cutover mulai dari DB kosong, dump ini jadi SATU-SATUNYA arsip data
# historis. Backup yang belum dites restore itu bukan backup.
source "$(dirname "$0")/_common.sh"
need_cmd mongodump mongorestore mongosh docker

# news_db dan threatintel pakai user Mongo yang BEDA dengan authSource beda
# (lihat ScraperNews/scripts/export_db.py) — gak ada satu URI yang nyakup
# dua-duanya, kecuali lu punya user root di authSource=admin.
#
#   punya root  : cukup export MONGO_URI="mongodb://root:PASS@10.8.20.78/?authSource=admin"
#   gak punya   : export MONGO_URI_NEWS_DB dan MONGO_URI_THREATINTEL sendiri-sendiri
#
# Per-DB menang atas MONGO_URI kalau dua-duanya di-set.
uri_for() {
  case "$1" in
    news_db)     printf '%s' "${MONGO_URI_NEWS_DB:-${MONGO_URI:-}}" ;;
    threatintel) printf '%s' "${MONGO_URI_THREATINTEL:-${MONGO_URI:-}}" ;;
    *)           die "db gak dikenal: $1" ;;
  esac
}

for db in news_db threatintel; do
  [ -n "$(uri_for "$db")" ] || die "gak ada URI buat '$db'. Set \$MONGO_URI (user root) atau \$MONGO_URI_$(echo "$db" | tr '[:lower:]' '[:upper:]'). Lihat docs/phases/PHASE_0_SALVAGE.md"
done

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUT="${CTI_BACKUP_DIR:-$HOME/cti-backups}/$STAMP"
mkdir -p "$OUT"

for db in news_db threatintel; do
  info "dump $db"
  mongodump --uri="$(uri_for "$db")" --db="$db" --out="$OUT" --gzip --quiet
done
ok "dump: $OUT ($(du -sh "$OUT" | cut -f1))"

# --- tes restore ---
info "mulai Mongo scratch buat verifikasi restore"
CID=$(docker run -d --rm -P mongo:7)
trap 'docker stop "$CID" >/dev/null 2>&1 || true' EXIT
PORT=$(docker port "$CID" 27017/tcp | head -1 | cut -d: -f2)

for i in $(seq 30); do
  docker exec "$CID" mongosh --quiet --eval 'db.adminCommand("ping")' >/dev/null 2>&1 && break
  [ "$i" = 30 ] && die "Mongo scratch gak siap-siap"
  sleep 1
done

info "restore ke scratch (port $PORT)"
mongorestore --uri="mongodb://localhost:$PORT" --gzip --quiet "$OUT"

info "bandingin jumlah dokumen"
FAIL=0
for db in news_db threatintel; do
  SRC_URI=$(uri_for "$db")
  for col in $(mongosh "$SRC_URI" --quiet --eval \
        "db.getSiblingDB('$db').getCollectionNames().join('\n')" 2>/dev/null); do
    SRC=$(mongosh "$SRC_URI" --quiet --eval \
        "db.getSiblingDB('$db').getCollection('$col').countDocuments({})")
    DST=$(mongosh "mongodb://localhost:$PORT" --quiet --eval \
        "db.getSiblingDB('$db').getCollection('$col').countDocuments({})")
    if [ "$SRC" = "$DST" ]; then
      printf '   %-28s %8s  ok\n' "$db.$col" "$SRC"
    else
      printf '   %-28s src=%s dst=%s  MISMATCH\n' "$db.$col" "$SRC" "$DST"
      FAIL=1
    fi
  done
done

[ "$FAIL" = 0 ] || die "verifikasi restore GAGAL — jangan lanjut cutover"
ok "restore terverifikasi, semua jumlah dokumen cocok"

cat <<TXT

Backup terverifikasi: $OUT

Salin ke luar host prod sekarang juga. Ini satu-satunya arsip data historis
lu setelah cutover ke DB kosong.

TXT
