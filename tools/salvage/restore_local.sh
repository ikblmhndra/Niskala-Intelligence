#!/usr/bin/env bash
# Fase 0.4 — Restore dump Mongo produksi ke container lokal, lalu VERIFIKASI.
#
# Dua gunanya:
#   1. Ngebuktiin backup-nya beneran bisa di-restore. Karena cutover mulai dari
#      DB kosong, dump ini SATU-SATUNYA arsip data historis — backup yang belum
#      pernah dites restore itu bukan backup.
#   2. Ngasih Mongo lokal berisi data asli buat kerja Fase 2 (rancang skema
#      Postgres) tanpa perlu nyentuh produksi.
source "$(dirname "$0")/_common.sh"
need_cmd docker

DUMP="${1:-$REPO_ROOT/legacy/dump}"
NAME="${CTI_MONGO_CONTAINER:-cti-mongo-legacy}"
PORT="${CTI_MONGO_PORT:-27017}"
[ -d "$DUMP" ] || die "dump gak ketemu: $DUMP"

if docker ps -a --format '{{.Names}}' | grep -qx "$NAME"; then
  info "container '$NAME' udah ada"
  docker start "$NAME" >/dev/null 2>&1 || true
else
  info "bikin container '$NAME' di port $PORT"
  docker run -d --name "$NAME" -p "$PORT:27017" \
    -v "${NAME}-data:/data/db" mongo:7 >/dev/null
fi

info "nunggu Mongo siap"
for i in $(seq 60); do
  docker exec "$NAME" mongosh --quiet --eval 'db.adminCommand("ping")' >/dev/null 2>&1 && break
  [ "$i" = 60 ] && die "Mongo gak siap-siap. Cek: docker logs $NAME"
  sleep 1
done
ok "Mongo siap di localhost:$PORT"

# 'admin' sengaja di-skip: isinya user/role instance lama, gak relevan buat
# container dev tanpa auth, dan bisa bikin restore gagal.
info "nyalin dump ke container"
docker exec "$NAME" rm -rf /tmp/dump
docker cp "$DUMP" "$NAME:/tmp/dump" >/dev/null

info "restore (admin di-skip)"
docker exec "$NAME" mongorestore --drop --quiet \
  --nsExclude 'admin.*' /tmp/dump 2>&1 | grep -vE '^\s*$' | tail -5

echo
info "verifikasi: jumlah dokumen file dump vs hasil restore"
FAIL=0
for db in "$DUMP"/*/; do
  dbname=$(basename "$db")
  [ "$dbname" = "admin" ] && continue
  for f in "$db"*.bson; do
    [ -e "$f" ] || continue
    col=$(basename "$f" .bson)
    case "$col" in *.metadata) continue;; esac
    DST=$(docker exec "$NAME" mongosh --quiet --eval \
      "db.getSiblingDB('$dbname').getCollection('$col').countDocuments({})" 2>/dev/null | tr -d '\r')
    SZ=$(du -h "$f" | cut -f1)
    if [ -n "$DST" ] && [ "$DST" -ge 0 ] 2>/dev/null; then
      printf '   %-22s %-26s %8s dok  (%s)\n' "$dbname" "$col" "$DST" "$SZ"
    else
      printf '   %-22s %-26s  GAGAL DIBACA\n' "$dbname" "$col"; FAIL=1
    fi
  done
done

[ "$FAIL" = 0 ] || die "sebagian collection gak kebaca setelah restore"
echo
ok "restore terverifikasi"
cat <<TXT

Mongo lokal berisi data produksi:  mongodb://localhost:$PORT
  jelajahi : docker exec -it $NAME mongosh
  stop     : docker stop $NAME
  nyalain  : docker start $NAME
  hapus    : docker rm -f $NAME && docker volume rm ${NAME}-data

Ini juga bikin techstack produksi bisa diambil buat context file Fase 0.5:
  docker exec $NAME mongosh --quiet --eval \\
    'JSON.stringify(db.getSiblingDB("threatintel").techstack.distinct("name"))'
TXT
