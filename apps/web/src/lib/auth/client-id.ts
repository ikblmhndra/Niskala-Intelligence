"use client";

/**
 * Client aktif (multi-tenant switcher) -- BUKAN rahasia (beda dari JWT),
 * jadi cookie biasa (readable JS), bukan httpOnly. Port `localStorage.
 * active_client_id` lama, dipindah ke cookie biar suatu saat Server
 * Component juga bisa baca kalau perlu (localStorage gak bisa dibaca
 * server-side sama sekali).
 */
const CLIENT_ID_COOKIE = "cti_client_id";

export function getActiveClientId(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(?:^|; )${CLIENT_ID_COOKIE}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

export function setActiveClientId(clientId: string): void {
  if (typeof document === "undefined") return;
  document.cookie = `${CLIENT_ID_COOKIE}=${encodeURIComponent(clientId)}; path=/; max-age=${60 * 60 * 24 * 365}; samesite=lax`;
}
