"use client";

import createClient from "openapi-fetch";

import type { paths } from "./schema";
import { getActiveClientId } from "@/lib/auth/client-id";

/**
 * `baseUrl` nunjuk ke proxy Next.js (`/api/proxy`), BUKAN `cti-api`
 * langsung -- browser gak pernah pegang JWT (httpOnly cookie), lihat
 * `docs/PROGRESS.md` Fase 8 keputusan #3. `schema.d.ts` di-generate dari
 * `docs/openapi.json` (`pnpm run gen:api`) -- path/method/body/response
 * semua ke-typecheck, drift backend ketahuan pas build, bukan runtime.
 */
export const api = createClient<paths>({ baseUrl: "/api/proxy" });

api.use({
  onRequest({ request }) {
    const clientId = getActiveClientId();
    if (clientId) {
      request.headers.set("X-Client-ID", clientId);
    }
    return request;
  },
});
