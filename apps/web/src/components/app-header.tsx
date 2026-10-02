"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuth } from "@/components/providers/auth-provider";
import { ChangelogDialog } from "@/components/changelog-dialog";
import { ClientSwitcher } from "@/components/client-switcher";
import { ThemeToggle } from "@/components/theme-toggle";
import { UserMenu } from "@/components/user-menu";
import { PLATFORM_NAME } from "@/lib/brand";
import { cn } from "@/lib/utils";

/** 9 route Fase 8 (docs/PROGRESS.md) -- padanan 8 tab lama + `/newsletter`
 * (route baru, gap yang ketemu pas survei). `/admin/users` di-guard
 * `role` di dalam `UserMenu`/halaman itu sendiri (bukan disembunyiin di
 * nav -- port perilaku lama: link tetep ada di DOM, cuma halamannya yang
 * nolak kalau bukan admin, lihat `deps.py::require_admin`).
 *
 * `/scrapers` (Fase 9, control plane scraper) -- keputusan user
 * (2026-09-25): halaman SENDIRI, bukan widget di `/dashboard` (yang
 * lama-nya "Scraper Health" numpang tab Dashboard). Read kebuka semua
 * user login (sama kayak halaman lain di nav ini), aksi tulis (trigger/
 * enable/disable/config) admin-only DI DALAM halaman-nya sendiri --
 * pola sama kayak `/admin/users` di atas, bukan disembunyiin dari nav. */
const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/newsroom", label: "Newsroom" },
  { href: "/cve", label: "CVE Tracker" },
  { href: "/intelligence", label: "Intelligence" },
  { href: "/exec", label: "Exec" },
  { href: "/xintel", label: "X Intel" },
  { href: "/recap", label: "Recap" },
  { href: "/newsletter", label: "Newsletter" },
  { href: "/scrapers", label: "Scrapers" },
  { href: "/admin/users", label: "Admin" },
] as const;

export function AppHeader() {
  const pathname = usePathname();
  const { user } = useAuth();

  return (
    <header className="sticky top-0 z-30 border-b border-border bg-surface/90 backdrop-blur supports-[backdrop-filter]:bg-surface/80">
      <div className="mx-auto flex w-full max-w-[1680px] flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 sm:px-6">
        <Link href="/dashboard" className="flex items-center gap-2.5 rounded-full outline-none focus-visible:ring-3 focus-visible:ring-ring/50">
          <span
            aria-hidden
            className="grid size-9 place-items-center rounded-full bg-primary font-heading text-base font-bold text-primary-foreground"
          >
            N
          </span>
          <span className="font-heading text-lg font-bold tracking-tight text-foreground">{PLATFORM_NAME}</span>
        </Link>
        <nav aria-label="Main" className="order-3 flex w-full gap-1 overflow-x-auto pb-1 lg:order-none lg:w-auto lg:flex-1 lg:justify-center lg:pb-0">
          {NAV_ITEMS.map((item) => {
            const active = pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "shrink-0 rounded-full px-4 py-2 text-sm font-medium outline-none transition-colors duration-200 focus-visible:ring-3 focus-visible:ring-ring/50",
                  active
                    ? "bg-primary text-primary-foreground shadow-sm"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground",
                )}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="ml-auto flex items-center gap-2 lg:ml-0">
          <ChangelogDialog />
          <ThemeToggle />
          {user && <ClientSwitcher user={user} />}
          <UserMenu />
        </div>
      </div>
    </header>
  );
}
