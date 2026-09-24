# `apps/web` -- CTI Platform frontend

Next.js App Router + TypeScript. Fase 8 (rewrite dari `ScraperNewsWeb`'s
vanilla JS/Jinja2 lama) -- lihat `docs/PROGRESS.md` buat status per-grup
dan `CLAUDE.md` buat gotcha shadcn/ui (Base UI, bukan Radix).

## Jalanin dev

Butuh `cti-api` (FastAPI) jalan duluan di `API_BASE_URL` (default
`http://localhost:8000`, `.env.local`) -- Next.js jadi BFF (Backend For
Frontend): browser gak pernah manggil `cti-api` langsung, semua lewat
`app/api/proxy/[...path]` (baca `src/proxy.ts` + `src/lib/auth/session.ts`
buat alasan arsitekturnya, keputusan #3 di `docs/PROGRESS.md` Fase 8).

```bash
pnpm install
pnpm dev
```

## Generate ulang tipe API

`src/lib/api/schema.d.ts` di-generate dari `docs/openapi.json` (root repo,
hasil Fase 7.7). Jalanin ulang abis backend nambah/ubah endpoint:

```bash
pnpm run gen:api
```
