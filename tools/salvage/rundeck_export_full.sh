#!/usr/bin/env bash
# Fase 0.2 — Ekspor definisi job Rundeck LENGKAP (termasuk command).
#
# Kenapa bukan pakai docs/legacy/rundeck-get-schedule.sh:
# script itu udah manggil /api/48/job/$ID yang balikin definisi penuh, tapi
# jq map({id,name,group,scheduleEnabled,schedule}) di akhir MEMBUANG bagian
# workflow-nya. Padahal di situ command aslinya berada, dan itu satu-satunya
# cara mapping "Artic Wolf" -> articThreat.py secara EKSAK, bukan nebak dari
# nama. 61 dari 233 job gak bisa dicocokin dari nama doang.
#
# Output:
#   docs/legacy/rundeck-jobs-full.json   definisi mentah penuh (arsip)
#   docs/legacy/rundeck-jobs-map.json    name -> script + schedule + enabled
source "$(dirname "$0")/_common.sh"
need_cmd curl jq
need_env RD_TOKEN

RD_URL="${RD_URL:-http://10.8.20.78:4440}"
PROJECT="${RD_PROJECT:-Threat-Information}"
API="${RD_API:-48}"
OUT="$REPO_ROOT/docs/legacy"
mkdir -p "$OUT"

api() { curl -sf -H "X-Rundeck-Auth-Token: $RD_TOKEN" -H "Accept: application/json" "$@"; }

info "ambil daftar job dari $RD_URL project=$PROJECT"
LIST=$(api "$RD_URL/api/$API/project/$PROJECT/jobs") \
  || die "gagal manggil API Rundeck — cek RD_TOKEN, RD_URL, dan konektivitas"

TOTAL=$(jq 'length' <<<"$LIST")
[ "$TOTAL" -gt 0 ] || die "0 job kebaca — project '$PROJECT' bener?"
info "$TOTAL job. Ngambil definisi penuh satu-satu..."

# SEMUA job diambil, bukan cuma yang scheduled — yang nonaktif masuk backlog
# migrasi, jadi definisinya tetap perlu diarsipkan.
: > "$OUT/.rundeck-raw.tmp"
i=0
while read -r id; do
  i=$((i+1))
  printf '\r  %d/%d' "$i" "$TOTAL" >&2
  api "$RD_URL/api/$API/job/$id" >> "$OUT/.rundeck-raw.tmp" || warn "job $id gagal"
done < <(jq -r '.[].id' <<<"$LIST")
echo >&2

# Endpoint job balikin objek yang disambung, bukan satu array.
jq -s 'map(if type=="array" then .[0] else . end)' \
  "$OUT/.rundeck-raw.tmp" > "$OUT/rundeck-jobs-full.json"
rm -f "$OUT/.rundeck-raw.tmp"
ok "definisi mentah -> docs/legacy/rundeck-jobs-full.json"

# Ekstrak command dari workflow. Rundeck naruhnya di beberapa bentuk:
#   exec        perintah shell langsung
#   script      isi script inline
#   scriptfile  path ke file di disk
jq 'map({
  id:        (.uuid // .id),
  name:      .name,
  group:     .group,
  enabled:   (.scheduleEnabled // false),
  schedule:  .schedule,
  commands: [ (.sequence.commands // [])[]
              | (.exec // .script // .scriptfile // .jobref.name // empty) ],
}) | map(. + {
  script: ( [ (.commands[]? | capture("(?<f>[A-Za-z0-9_./-]+\\.py)").f) ][0] // null ),
  workdir: ( [ (.commands[]? | capture("cd\\s+(?<d>/[A-Za-z0-9_./-]+)").d) ][0] // null )
})' "$OUT/rundeck-jobs-full.json" > "$OUT/rundeck-jobs-map.json"

MAPPED=$(jq '[.[] | select(.script != null)] | length' "$OUT/rundeck-jobs-map.json")
ENABLED=$(jq '[.[] | select(.enabled)] | length' "$OUT/rundeck-jobs-map.json")
ok "peta -> docs/legacy/rundeck-jobs-map.json"
echo "   job total        : $TOTAL"
echo "   aktif            : $ENABLED"
echo "   ketemu script .py : $MAPPED"

if [ "$MAPPED" -lt $((TOTAL / 2)) ]; then
  warn "cuma $MAPPED job yang kedeteksi script .py-nya."
  warn "Cek satu definisi buat lihat bentuk command-nya:"
  warn "  jq '.[0].sequence.commands' docs/legacy/rundeck-jobs-full.json"
fi

cat <<TXT

Path workdir unik (ini ngungkap codebase mana aja yang dijadwalin Rundeck):
$(jq -r '[.[].workdir] | map(select(. != null)) | unique | .[]' "$OUT/rundeck-jobs-map.json" 2>/dev/null | sed 's/^/  /')

Berikutnya: kedua file itu di-commit, terus jadwalnya dipakai ngisi
ScraperMeta.schedule waktu codemod Fase 4.
TXT
