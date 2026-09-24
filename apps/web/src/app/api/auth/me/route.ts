import { NextResponse } from "next/server";

import { getSessionToken } from "@/lib/auth/session";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://localhost:8000";

/**
 * Dipanggil `AuthProvider` (Client Component) pas mount -- satu-satunya
 * cara klien tau siapa yang login, karena cookie session-nya httpOnly
 * (gak bisa di-decode langsung di browser). `cti-api` sendiri yang jadi
 * sumber kebenaran role/client_ids (bukan decode JWT manual di sini).
 */
export async function GET(): Promise<NextResponse> {
  const token = await getSessionToken();
  if (!token) {
    return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${API_BASE_URL}/api/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
  } catch {
    return NextResponse.json({ detail: "cti-api unreachable" }, { status: 502 });
  }

  const payload = await upstream.json().catch(() => null);
  return NextResponse.json(payload, { status: upstream.status });
}
