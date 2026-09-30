#!/bin/sh
# Sertifikat TLS self-signed untuk edge nginx (Fase 10.G). Dijalankan otomatis oleh entrypoint image
# nginx (/docker-entrypoint.d/) SEBELUM nginx start, jadi `docker compose up -d` langsung HTTPS tanpa
# langkah manual.
#
# Aturan:
#   - cti.crt + cti.key SUDAH ADA dan BUKAN buatan skrip ini (subject tanpa penanda di bawah)
#     -> itu sertifikat operator (CA internal). TIDAK PERNAH disentuh, apa pun env-nya.
#   - belum ada                                  -> dibuat.
#   - buatan skrip ini tapi daftar host berubah, kurang dari NGINX_TLS_RENEW_DAYS hari lagi
#     kedaluwarsa, atau kuncinya tak cocok dengan sertifikat   -> dibuat ulang.
#   - selain itu                                 -> dipakai apa adanya (fingerprint stabil antar restart,
#     jadi orang yang sudah memercayainya tidak perlu mengulang).
#
# Env: NGINX_TLS_HOSTS  nama host / IPv4 yang dipakai orang membuka platform, dipisah koma
#                       (masuk SAN; `localhost` dan `127.0.0.1` SELALU ikut). IPv6 belum didukung.
#      NGINX_TLS_DAYS   masa berlaku sertifikat baru (default 365)
#      NGINX_TLS_RENEW_DAYS  ambang perpanjangan (default 30)
set -eu

TLS_DIR=/etc/nginx/tls
CRT="$TLS_DIR/cti.crt"
KEY="$TLS_DIR/cti.key"
DAYS="${NGINX_TLS_DAYS:-365}"
RENEW_DAYS="${NGINX_TLS_RENEW_DAYS:-30}"
OWNER_TAG="CTI Platform (self-signed)"

log() { echo "05-selfsigned-cert.sh: $*"; }
die() { echo "05-selfsigned-cert.sh: GAGAL: $*" >&2; exit 1; }

case "$DAYS" in '' | *[!0-9]*) die "NGINX_TLS_DAYS harus angka (dapat '$DAYS')" ;; esac
case "$RENEW_DAYS" in '' | *[!0-9]*) die "NGINX_TLS_RENEW_DAYS harus angka (dapat '$RENEW_DAYS')" ;; esac

is_ipv4() {
    # empat oktet 0-255; pola sudah dijamin hanya angka dan titik sebelum dipanggil
    printf '%s\n' "$1" | awk -F. 'NF == 4 && $1 != "" && $2 != "" && $3 != "" && $4 != "" && $1 <= 255 && $2 <= 255 && $3 <= 255 && $4 <= 255 { ok = 1 } END { exit ok ? 0 : 1 }'
}

# --- daftar SAN yang diinginkan ------------------------------------------------------------------
san="DNS:localhost,IP:127.0.0.1"
cn="cti"
first=1
hosts_list="${NGINX_TLS_HOSTS:-}"
old_ifs=$IFS
set -f                       # `*.corp.local` jangan diperluas glob
IFS=,
for raw in $hosts_list; do   # pemecahan per koma terjadi SEKALI di sini; IFS boleh dipulihkan di badan loop
    IFS=$old_ifs
    h=$(printf '%s' "$raw" | tr -d '[:space:]')
    [ -n "$h" ] || continue
    case "$h" in
        *:*) die "IPv6 belum didukung generator ini ('$h'); pasang cti.crt/cti.key sendiri" ;;
        *[!A-Za-z0-9.*_-]*) die "nama host tidak valid: '$h'" ;;
    esac
    case "$h" in
        *[!0-9.]*) entry="DNS:$h" ;;
        *)
            is_ipv4 "$h" || die "alamat IPv4 tidak valid: '$h'"
            entry="IP:$h"
            ;;
    esac
    case ",$san," in *",$entry,"*) continue ;; esac
    san="$san,$entry"
    if [ "$first" -eq 1 ]; then
        cn="$h"
        first=0
    fi
done
IFS=$old_ifs
set +f

# --- keputusan: sentuh atau tidak ----------------------------------------------------------------
have_crt=0
have_key=0
[ -f "$CRT" ] && have_crt=1
[ -f "$KEY" ] && have_key=1

reason=""
if [ "$have_crt" -eq 1 ] && [ "$have_key" -eq 1 ]; then
    subject=$(openssl x509 -noout -subject -in "$CRT" 2>/dev/null) \
        || die "$CRT bukan sertifikat PEM yang terbaca"
    case "$subject" in
        *"$OWNER_TAG"*) ;;
        *) log "sertifikat sendiri terdeteksi ($CRT) -- tidak diubah"; exit 0 ;;
    esac

    current=$(openssl x509 -noout -ext subjectAltName -in "$CRT" 2>/dev/null \
        | tail -n +2 | tr -d ' \n' | sed 's/IPAddress:/IP:/g' || true)
    crt_pub=$(openssl x509 -noout -pubkey -in "$CRT" 2>/dev/null | openssl sha256 2>/dev/null || true)
    key_pub=$(openssl pkey -pubout -in "$KEY" 2>/dev/null | openssl sha256 2>/dev/null || true)
    if [ "$current" != "$san" ]; then
        reason="daftar host berubah"
    elif [ -z "$crt_pub" ] || [ "$crt_pub" != "$key_pub" ]; then
        reason="kunci tidak cocok dengan sertifikat"
    elif ! openssl x509 -checkend $((RENEW_DAYS * 86400)) -noout -in "$CRT" >/dev/null 2>&1; then
        reason="kedaluwarsa dalam <= $RENEW_DAYS hari"
    fi
    if [ -z "$reason" ]; then
        log "sertifikat self-signed masih valid ($san) -- dipakai apa adanya"
        exit 0
    fi
elif [ "$have_crt" -eq 1 ] || [ "$have_key" -eq 1 ]; then
    die "hanya salah satu dari cti.crt / cti.key yang ada di $TLS_DIR; lengkapi pasangannya atau hapus keduanya"
else
    reason="belum ada"
fi

# --- buat baru: ke direktori sementara dulu, baru dipindah -----------------------------------------
umask 077
tmp=$(mktemp -d "$TLS_DIR/.gen.XXXXXX") || die "tidak bisa menulis ke $TLS_DIR (mount read-only?)"
trap 'rm -rf "$tmp"' EXIT

openssl req -x509 -newkey rsa:2048 -nodes -sha256 -days "$DAYS" \
    -keyout "$tmp/cti.key" -out "$tmp/cti.crt" \
    -subj "/O=$OWNER_TAG/CN=$cn" \
    -addext "subjectAltName=$san" \
    -addext "basicConstraints=critical,CA:FALSE" \
    -addext "keyUsage=critical,digitalSignature,keyEncipherment" \
    -addext "extendedKeyUsage=serverAuth" >/dev/null 2>&1 \
    || die "openssl gagal membuat sertifikat (SAN: $san)"

chmod 600 "$tmp/cti.key"
chmod 644 "$tmp/cti.crt"
mv -f "$tmp/cti.key" "$KEY"
mv -f "$tmp/cti.crt" "$CRT"

log "sertifikat self-signed dibuat ($reason): SAN=$san, berlaku $DAYS hari"
log "$(openssl x509 -noout -fingerprint -sha256 -in "$CRT")"
