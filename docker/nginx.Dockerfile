# Edge proxy (Fase 10.G): TLS + reverse proxy ke `web`. Image sendiri, bukan nginx polos, karena:
#   - butuh `openssl` buat bikin sertifikat self-signed (nginx:alpine tidak membawanya);
#   - config di-bake ke image, jadi tidak ada file config di host yang bisa lupa ikut dipindah.
# Tag TIDAK ikut CTI_TAG (lihat docker-compose.yml): rollback aplikasi tidak menyentuh edge.
FROM nginx:1.27-alpine

RUN apk add --no-cache openssl \
    && rm -f /etc/nginx/conf.d/default.conf

# Template diproses entrypoint resmi nginx (envsubst -> /etc/nginx/conf.d/cti.conf).
COPY docker/nginx/templates/ /etc/nginx/templates/
# Entrypoint nginx menjalankan /docker-entrypoint.d/*.sh berurutan SEBELUM nginx start.
COPY docker/nginx/05-selfsigned-cert.sh /docker-entrypoint.d/05-selfsigned-cert.sh
# Loop latar belakang: sertifikat self-signed diperbarui tanpa restart container (tiap 24 jam).
COPY docker/nginx/06-cert-renew-loop.sh /docker-entrypoint.d/06-cert-renew-loop.sh
RUN chmod 755 /docker-entrypoint.d/05-selfsigned-cert.sh /docker-entrypoint.d/06-cert-renew-loop.sh

# Hanya variabel NGINX_* yang disubstitusi ke template -- variabel nginx ($host, $remote_addr, ...)
# dan env lain tak pernah ikut tersentuh.
ENV NGINX_ENVSUBST_FILTER=^NGINX_ \
    NGINX_PUBLIC_HTTPS_PORT=443

# Healthcheck lewat HTTP POLOS di listener loopback (127.0.0.1:8081, lihat template), BUKAN https: `wget`
# busybox memakai proses anak `ssl_client` untuk TLS; prosesnya menjadi yatim, di-reap nginx (PID 1) yang
# menulis 2 baris `notice` ke log tiap 15 dtk (~11.500 baris/hari). Yang dicek tetap "nginx hidup dan
# menjawab"; konfigurasi/sertifikat yang rusak membuat nginx gagal start/reload, bukan lolos diam-diam.
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:8081/nginx-health || exit 1
