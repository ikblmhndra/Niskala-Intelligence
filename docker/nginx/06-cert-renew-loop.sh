#!/bin/sh
# Pembaruan sertifikat self-signed TANPA restart container (Fase 10.G). 05-selfsigned-cert.sh hanya
# jalan saat container start; nginx yang berjalan lebih dari setahun tanpa restart akan kedaluwarsa
# diam-diam (kejadian klasik "kemarin masih jalan"). Skrip ini memulai loop latar belakang: tiap
# NGINX_TLS_RENEW_CHECK_SECONDS (default 24 jam) 05-selfsigned-cert.sh dijalankan ulang, dan kalau
# sertifikatnya berubah -> `nginx -s reload`.
#
# Sertifikat operator tidak pernah diubah oleh 05, jadi tidak pernah ada reload karenanya (mengganti
# file sendiri tetap = `docker compose restart nginx`).
set -eu

INTERVAL="${NGINX_TLS_RENEW_CHECK_SECONDS:-86400}"
case "$INTERVAL" in
    '' | 0* | *[!0-9]*)
        echo "06-cert-renew-loop.sh: GAGAL: NGINX_TLS_RENEW_CHECK_SECONDS harus bilangan bulat > 0 (dapat '$INTERVAL')" >&2
        exit 1
        ;;
esac

fp() { openssl x509 -noout -fingerprint -sha256 -in /etc/nginx/tls/cti.crt 2>/dev/null || true; }

(
    while sleep "$INTERVAL"; do
        before=$(fp)
        if /docker-entrypoint.d/05-selfsigned-cert.sh; then
            if [ "$(fp)" != "$before" ]; then
                echo "06-cert-renew-loop.sh: sertifikat berubah -> nginx -s reload"
                nginx -s reload || echo "06-cert-renew-loop.sh: reload GAGAL" >&2
            fi
        else
            echo "06-cert-renew-loop.sh: pembaruan sertifikat gagal; sertifikat lama tetap dipakai" >&2
        fi
    done
) &
