"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { AppHeader } from "@/components/app-header";
import { useAuth } from "@/components/providers/auth-provider";

/** Shell buat SEMUA route ber-auth (9 route Fase 8) -- `proxy.ts` udah
 * nge-redirect optimistic di edge kalau cookie gak ada sama sekali, guard
 * di sini nangkep kasus SISANYA: cookie ada tapi ternyata invalid/expired
 * (baru ketauan pas `/api/auth/me` beneran dipanggil -- proxy.ts SENGAJA
 * gak decode JWT, lihat docstring situ). */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (status === "unauthenticated") {
      router.replace("/login");
    }
  }, [status, router]);

  if (status !== "authenticated") {
    return null;
  }

  return (
    <div className="flex min-h-screen flex-col">
      <AppHeader />
      <main className="mx-auto w-full max-w-[1680px] flex-1 p-4 sm:p-6">{children}</main>
    </div>
  );
}
