import "server-only";

import { cookies } from "next/headers";

/**
 * Cookie-nya NYIMPEN JWT asli dari `cti-api` (`access_token` mentah dari
 * `POST /api/auth/login`) -- BUKAN sesi terpisah yang di-encode ulang
 * (`jose`/`iron-session`). `cti-api` udah validasi JWT-nya sendiri
 * (`security.py::decode_token`) tiap kali proxy manggil dia -- gak ada
 * DB sesi kedua yang perlu disinkronkan di sisi Next.js.
 */
const SESSION_COOKIE = "cti_session";

/** httpOnly -- keputusan arsitektur Fase 8 Grup A: JS klien gak pernah
 * baca token ini (beda dari app lama yang naruh JWT di `localStorage`).
 * Konsekuensinya: SEMUA request ber-auth dari Client Component harus
 * lewat proxy Next.js (`app/api/proxy/[...path]`), gak pernah fetch
 * `cti-api` langsung dari browser. */
export async function setSessionCookie(token: string): Promise<void> {
  const cookieStore = await cookies();
  cookieStore.set(SESSION_COOKIE, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    // Gak pasang `expires` eksplisit -- umur token dikontrol JWT_EXPIRE_MIN
    // (`cti_core.config`, default 480 menit) yang udah di-encode DI DALAM
    // JWT itu sendiri; cookie session (habis pas browser ditutup) cukup,
    // `cti-api` yang nolak token expired lewat validasi `decode_token()`.
  });
}

export async function getSessionToken(): Promise<string | undefined> {
  const cookieStore = await cookies();
  return cookieStore.get(SESSION_COOKIE)?.value;
}

export async function clearSessionCookie(): Promise<void> {
  const cookieStore = await cookies();
  cookieStore.delete(SESSION_COOKIE);
}

export const SESSION_COOKIE_NAME = SESSION_COOKIE;
