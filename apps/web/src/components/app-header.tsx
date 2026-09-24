"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuth } from "@/components/providers/auth-provider";
import { ChangelogDialog } from "@/components/changelog-dialog";
import { ClientSwitcher } from "@/components/client-switcher";
import { UserMenu } from "@/components/user-menu";
import { cn } from "@/lib/utils";

/** 9 route Fase 8 (docs/PROGRESS.md) -- padanan 8 tab lama + `/newsletter`
 * (route baru, gap yang ketemu pas survei). `/admin/users` di-guard
 * `role` di dalam `UserMenu`/halaman itu sendiri (bukan disembunyiin di
 * nav -- port perilaku lama: link tetep ada di DOM, cuma halamannya yang
 * nolak kalau bukan admin, lihat `deps.py::require_admin`). */
const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/newsroom", label: "Newsroom" },
  { href: "/cve", label: "CVE Tracker" },
  { href: "/intelligence", label: "Intelligence" },
  { href: "/exec", label: "Exec" },
  { href: "/xintel", label: "X Intel" },
  { href: "/recap", label: "Recap" },
  { href: "/newsletter", label: "Newsletter" },
  { href: "/admin/users", label: "Admin" },
] as const;

export function AppHeader() {
  const pathname = usePathname();
  const { user } = useAuth();

  return (
    <header className="border-b border-border bg-surface">
      <div className="flex items-center justify-between px-4 py-2">
        <span className="font-heading text-sm tracking-widest text-primary">CTI PLATFORM</span>
        <div className="flex items-center gap-2">
          <ChangelogDialog />
          {user && <ClientSwitcher user={user} />}
          <UserMenu />
        </div>
      </div>
      <nav className="flex gap-1 overflow-x-auto px-4 pb-2">
        {NAV_ITEMS.map((item) => {
          const active = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "shrink-0 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                active
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground",
              )}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
    </header>
  );
}
