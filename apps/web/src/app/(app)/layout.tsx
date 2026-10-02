"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { AppSidebar, AppTopbar } from "@/components/app-header";
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
    <div className="flex min-h-screen">
      <AppSidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <AppTopbar />
        <main className="mx-auto w-full max-w-[1600px] flex-1 p-4 sm:p-8">{children}</main>
      </div>
    </div>
  );
}
