#!/usr/bin/env bash
# Deploy CTI platform dari NOL di host baru (tanpa Mongo/stack lama). Idempoten: aman dijalankan ulang,
# tidak pernah menghapus volume atau data.
#
#   cp .env.prod.template .env              # isi semua nilai (jangan tempel secret ke chat/tiket)
#   cp docker/stack.env.example docker/stack.env   # ganti POSTGRES_PASSWORD, NGINX_TLS_HOSTS, port
#   make fresh-deploy                       # atau: bash tools/ops/fresh_deploy.sh
#
# Urutan (sama dengan docs/CUTOVER_RUNBOOK.md bagian 3, minus langkah yang butuh stack lama):
#   0 cek prasyarat  1 build image  2 cek secret (probe live, baca-doang)  3 postgres+redis+migrasi+api
#   4 seed data referensi bawaan  5 admin pertama (auth/init)  6 sinkron katalog ATT&CK
#   7 worker  8 beat TERAKHIR  9 web + nginx  -> ringkasan
#
# Opsi:  --skip-build  --skip-secret-check  --skip-nginx  -h|--help
# Env:   ADMIN_USER (default "admin")  CTI_ENV_FILE (default .env)  CTI_STACK_ENV (default docker/stack.env)
#        COMPOSE_PROJECT_NAME (mis. untuk latihan di mesin yang sudah punya stack lain)
#
# Password admin dibuat acak dan ditulis ke secrets/admin_password (mode 600) -- TIDAK pernah dicetak.
# Ganti lewat UI setelah login pertama lalu hapus file itu.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."

ENV_FILE="${CTI_ENV_FILE:-.env}"
STACK_ENV="${CTI_STACK_ENV:-docker/stack.env}"
ADMIN_USER="${ADMIN_USER:-admin}"
ADMIN_PW_FILE="secrets/admin_password"
SKIP_BUILD=0 SKIP_SECRET_CHECK=0 SKIP_NGINX=0

for arg in "$@"; do
  case "$arg" in
    --skip-build) SKIP_BUILD=1 ;;
    --skip-secret-check) SKIP_SECRET_CHECK=1 ;;
    --skip-nginx) SKIP_NGINX=1 ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "opsi tidak dikenal: $arg (lihat --help)" >&2; exit 2 ;;
  esac
done

say() { printf '\n==> %s\n' "$*"; }
warn() { printf '  [PERINGATAN] %s\n' "$*" >&2; }
die() { printf '\n[GAGAL] %s\n' "$*" >&2; exit 1; }

export CTI_ENV_FILE="$ENV_FILE"
dc() { docker compose --env-file "$STACK_ENV" --profile app "$@"; }
stack_var() { # nilai variabel dari stack.env tanpa komentar inline; kosong kalau tidak ada
  { grep -E "^$1=" "$STACK_ENV" || true; } | tail -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*$//; s/[[:space:]]*$//'
}

# ------------------------------------------------------------------------------------------------
say "0/9 cek prasyarat"
command -v docker >/dev/null || die "docker tidak ditemukan"
docker compose version >/dev/null 2>&1 || die "plugin 'docker compose' tidak ditemukan"
docker info >/dev/null 2>&1 || die "daemon docker tidak jalan / user ini tidak boleh memakainya"
command -v python3 >/dev/null || die "python3 dibutuhkan (generator password + pengecekan env)"

if [ ! -f "$ENV_FILE" ]; then
  cp .env.prod.template "$ENV_FILE"; chmod 600 "$ENV_FILE"
  die "$ENV_FILE belum ada -- saya salinkan dari .env.prod.template. Isi semua nilainya (terutama baris
       bertanda [ ] ROTASI), lalu jalankan ulang."
fi
if [ ! -f "$STACK_ENV" ]; then
  cp docker/stack.env.example "$STACK_ENV"
  die "$STACK_ENV belum ada -- saya salinkan dari docker/stack.env.example. Ganti POSTGRES_PASSWORD
       (harus sama dengan password di DATABASE__URL), NGINX_TLS_HOSTS, dan port bila perlu, lalu jalankan ulang."
fi
if grep -q 'GANTI_INI' "$ENV_FILE"; then
  grep -n 'GANTI_INI' "$ENV_FILE" | cut -d: -f1 | sed 's/^/  baris /' >&2
  die "$ENV_FILE masih berisi placeholder GANTI_INI (baris di atas)."
fi
[ "$(stack_var POSTGRES_PASSWORD)" != "cti" ] || die "POSTGRES_PASSWORD di $STACK_ENV masih default 'cti' -- ganti."

# Rahasia internal (bukan key provider) yang kosong di template: bangkitkan acak, jangan paksa user mengarang.
python3 - "$ENV_FILE" <<'PY'
import re, secrets, sys

path = sys.argv[1]
text = open(path, encoding="utf-8").read()
made = []
for key in ("AUTH__JWT_SECRET", "AUTH__SESSION_SECRET_KEY"):
    pat = re.compile(rf"^{key}=[ \t]*(#.*)?$", re.M)
    if pat.search(text):
        text = pat.sub(f"{key}={secrets.token_urlsafe(48)}", text, count=1)
        made.append(key)
if made:
    open(path, "w", encoding="utf-8").write(text)
    print("  dibangkitkan acak (tadinya kosong): " + ", ".join(made))
PY

python3 - "$ENV_FILE" "$STACK_ENV" <<'PY' || die "password Postgres di $STACK_ENV tidak cocok dengan DATABASE__URL / DATABASE__SYNC_URL di $ENV_FILE."
import re, sys
from urllib.parse import unquote, urlsplit

def read(path):
    out = {}
    for line in open(path, encoding="utf-8"):
        m = re.match(r"^([A-Z0-9_]+)=(.*)$", line.rstrip("\n"))
        if m:
            out[m.group(1)] = re.sub(r"\s+#.*$", "", m.group(2)).strip()
    return out

app, stack = read(sys.argv[1]), read(sys.argv[2])
want = stack.get("POSTGRES_PASSWORD", "")
bad = [k for k in ("DATABASE__URL", "DATABASE__SYNC_URL")
       if unquote(urlsplit(app.get(k, "")).password or "") != want]
sys.exit(1 if bad or not want else 0)
PY
echo "  ok: docker, env aplikasi terisi, password Postgres konsisten"

TAG="$(stack_var CTI_TAG)"; TAG="${TAG:-latest}"
API_PORT="$(stack_var API_PORT)"; API_PORT="${API_PORT:-8000}"

wait_ready() { # wait_ready <service> [detik]  -- healthy, atau running kalau service tanpa healthcheck
  local svc="$1" limit="${2:-240}" i=0 cid st
  while [ "$i" -lt "$limit" ]; do
    cid="$(dc ps -q "$svc" 2>/dev/null | head -1)"
    if [ -n "$cid" ]; then
      st="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$cid")"
      case "$st" in
        healthy|running) return 0 ;;
        exited|dead) break ;;
      esac
    fi
    sleep 3; i=$((i + 3))
  done
  warn "$svc tidak siap (status: ${st:-tidak ada}). 30 baris log terakhir:"
  dc logs --no-color --tail 30 "$svc" >&2 || true
  die "$svc gagal naik."
}

# ------------------------------------------------------------------------------------------------
if [ "$SKIP_BUILD" -eq 1 ]; then
  say "1/9 build dilewati (--skip-build)"
else
  say "1/9 build image (pertama kali bisa 10-20 menit)"
  dc build
fi

if [ "$SKIP_SECRET_CHECK" -eq 1 ]; then
  say "2/9 cek secret dilewati (--skip-secret-check)"
else
  say "2/9 cek secret: probe live baca-doang ke LLM/Telegram/NVD/GitHub/twitterapi.io/X"
  # `compose run` (bukan `docker run --env-file`): compose membuang komentar inline di .env, docker run tidak.
  dc run --rm --no-deps -T -v "$PWD/tools:/tools:ro" --entrypoint python worker \
    /tools/ops/check_secrets.py || die "check_secrets gagal -- betulkan key yang ditolak di $ENV_FILE
       (key opsional yang kosong tidak masalah; LLM dan Telegram wajib). Lanjutkan paksa: --skip-secret-check."
fi

say "3/9 postgres + redis, migrasi skema, api"
dc up -d postgres redis
wait_ready postgres; wait_ready redis
dc up -d api            # menarik service `migrate` (one-shot, alembic upgrade head) lebih dulu
wait_ready api

say "4/9 seed data referensi bawaan (threat actor, demonym, allowlist IOC)"
dc run --rm --no-deps -T -v "$PWD/tools:/tools:ro" -v "$PWD/tools/seed/reference:/dump:ro" \
  --entrypoint sh worker -c '
    pip install --target /tmp/pm -q pymongo &&
    PYTHONPATH=/tmp/pm python /tools/seed/fase5_reference_data.py --dump-dir /dump' \
  || die "seed data referensi gagal (lihat pesan di atas)."

say "5/9 admin pertama ($ADMIN_USER) lewat POST /api/auth/init"
mkdir -p secrets && chmod 700 secrets
NEWPW="$ADMIN_PW_FILE.new"
( umask 077; python3 - > "$NEWPW" <<'PY'
import secrets, string
rng = secrets.SystemRandom()
pools = [string.ascii_uppercase, string.ascii_lowercase, string.digits, "-_.!@#%^*+="]
chars = [rng.choice(p) for p in pools] + [rng.choice("".join(pools)) for _ in range(24)]
rng.shuffle(chars)
print("".join(chars))
PY
)
set +e
python3 -c '
import json, sys
print(json.dumps({"username": sys.argv[1], "password": open(sys.argv[2]).read().strip()}))' \
  "$ADMIN_USER" "$NEWPW" \
| dc exec -T api python -c '
import json, sys, urllib.error, urllib.request
body = sys.stdin.buffer.read()
req = urllib.request.Request("http://127.0.0.1:8000/api/auth/init", data=body,
                             headers={"Content-Type": "application/json"})
try:
    urllib.request.urlopen(req, timeout=30); sys.exit(0)
except urllib.error.HTTPError as e:
    raw = e.read().decode("utf-8", "replace")
    if e.code == 409: sys.exit(3)
    try:
        d = json.loads(raw).get("detail")
    except ValueError:
        d = None
    if isinstance(d, list):   # 422 pydantic: JANGAN cetak "input" (berisi password)
        d = "; ".join(str(x.get("loc")) + " " + str(x.get("msg")) for x in d if isinstance(x, dict))
    print("HTTP %s: %s" % (e.code, d if isinstance(d, str) else "(lihat log api)"), file=sys.stderr)
    sys.exit(1)
'
rc=$?
set -e
case "$rc" in
  0) mv "$NEWPW" "$ADMIN_PW_FILE"; echo "  admin '$ADMIN_USER' dibuat; password ada di $ADMIN_PW_FILE (mode 600)" ;;
  3) rm -f "$NEWPW"; echo "  sudah ada user di database -- admin tidak dibuat ulang (file password lama, kalau ada, tidak disentuh)" ;;
  *) rm -f "$NEWPW"; die "pembuatan admin gagal (kode $rc)." ;;
esac

say "6/9 sinkron katalog ATT&CK (butuh akses keluar ke GitHub; tanpa ini TTP belum dinormalisasi)"
if ! dc exec -T api python - <<'PY'
import asyncio, json, sys
from cti_core.db.engine import async_session
from cti_core.db.repositories.attack import AsyncAttackSyncRepo

async def main() -> int:
    async with async_session() as s:
        repo = AsyncAttackSyncRepo(s)
        await repo.sync_all_domains()
        status = await repo.get_sync_status()
    for row in status:
        print("  ", json.dumps(row, default=str)[:160])
    return 1 if any(r.get("status") == "never" for r in status) else 0

sys.exit(asyncio.run(main()))
PY
then
  warn "sinkron ATT&CK belum lengkap (jaringan keluar ke GitHub diblokir?). Platform tetap naik; task
       periodik akan mencoba lagi, atau tekan tombol Sync di UI. Artikel yang masuk sebelum katalog terisi
       bisa punya TTP yang belum dinormalisasi."
fi

say "7/9 worker (ringan, browser, nlp)"
dc up -d worker worker-browser worker-nlp
wait_ready worker; wait_ready worker-browser; wait_ready worker-nlp 360

say "8/9 beat -- penembak jadwal, SENGAJA terakhir"
dc up -d beat
wait_ready beat 60
sleep 5
leaders="$(dc logs --no-color beat 2>&1 | grep -c 'beat_leader' || true)"
[ "$leaders" -eq 1 ] || warn "baris beat_leader di log = $leaders (harus tepat 1). Periksa: docker compose logs beat"

say "9/9 web$([ "$SKIP_NGINX" -eq 1 ] || echo ' + nginx')"
dc up -d web
wait_ready web
if [ "$SKIP_NGINX" -eq 0 ]; then
  dc up -d nginx
  wait_ready nginx
fi

HTTPS_PORT="$(stack_var NGINX_HTTPS_PORT)"; HTTPS_PORT="${HTTPS_PORT:-443}"
HOSTS="$(stack_var NGINX_TLS_HOSTS)"
say "SELESAI"
dc ps --format 'table {{.Service}}\t{{.Status}}'
cat <<EOF

Buka   : https://${HOSTS%%,*}$([ "$HTTPS_PORT" = 443 ] || echo ":$HTTPS_PORT")   (sertifikat self-signed: browser akan memperingatkan)
Login  : user '$ADMIN_USER', password di $ADMIN_PW_FILE  -> ganti lewat UI, lalu hapus file itu
Health : curl -fs http://127.0.0.1:${API_PORT}/healthz

Yang MASIH harus diisi manual lewat UI (tanpa ini beberapa scraper sengaja idle):
  - client + negara, user lain, techstack (tanpa ini new_cve kosong), akun X yang dipantau (tanpa ini monitor_x idle)
Dianjurkan sebelum dipakai: pasang timer backup Postgres (docs/PROD_PREP.md, docker/ops/cti-pg-backup.*).
Scraper pertama kali jalan = mode "cold start": maks 5 item per scraper. Detail: README.md dan docs/CUTOVER_RUNBOOK.md.
EOF
