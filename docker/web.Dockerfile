# syntax=docker/dockerfile:1.7
#
# Image `web` (Next.js 16, output "standalone") -- plan §10. Context = ROOT repo:
#   docker build -f docker/web.Dockerfile -t cti-web .
#
# Env RUNTIME yang dibaca server: cuma `API_BASE_URL` (alamat cti-api, dibaca
# Route Handler proxy -- gak pernah masuk bundle browser, jadi BUKAN build arg).
# Cookie session `secure` di NODE_ENV=production => browser cuma nerima lewat
# HTTPS (atau http://localhost): TLS dipegang proxy di depan (nginx).

ARG NODE_IMAGE=node:22-bookworm-slim

# ------------------------------------------------------------------- deps --
FROM ${NODE_IMAGE} AS deps
# `npm_config_fetch_retries`: registry npm sesekali mutus koneksi di tengah
# download (kejadian nyata di staging: "SocketError: other side closed").
ENV PNPM_HOME=/pnpm PATH="/pnpm:${PATH}" CI=true \
    npm_config_fetch_retries=5 npm_config_fetch_retry_mintimeout=2000
WORKDIR /app
COPY apps/web/package.json apps/web/pnpm-lock.yaml apps/web/pnpm-workspace.yaml ./
# Versi pnpm dari `packageManager` di package.json (corepack). Corepack GAK
# retry download tarball pnpm-nya sendiri, jadi diulang manual; gagal semua
# percobaan = build gagal (`exit 1`), bukan lanjut tanpa pnpm.
RUN corepack enable \
    && for i in 1 2 3 4 5; do corepack install && exit 0; echo "corepack install gagal (percobaan $i), ulangi..."; sleep 5; done; exit 1
RUN --mount=type=cache,target=/pnpm/store \
    pnpm install --frozen-lockfile

# ------------------------------------------------------------------ build --
FROM deps AS build
ENV NEXT_TELEMETRY_DISABLED=1
COPY apps/web ./
RUN pnpm build

# ----------------------------------------------------------------- runner --
FROM ${NODE_IMAGE} AS runner
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000
WORKDIR /app
# `standalone` = server.js + node_modules hasil tracing; aset statis + public
# TIDAK ikut otomatis (Next nyaranin dilayani CDN), jadi disalin manual.
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
COPY --from=build --chown=node:node /app/public ./public
USER node
EXPOSE 3000
# `/login` = route publik (proxy.ts gak nge-redirect) -> 200 kalau server hidup.
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD node -e "fetch('http://127.0.0.1:3000/login').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["node", "server.js"]
