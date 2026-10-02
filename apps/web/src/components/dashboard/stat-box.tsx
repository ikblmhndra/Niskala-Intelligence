import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

interface StatBoxProps {
  label: string;
  value: number | string | undefined;
  sub: ReactNode;
  className?: string;
}

/** Port `.dash-stat-box` dari `newsroom.html`/`custom.css` lama. */
export function StatBox({ label, value, sub, className }: StatBoxProps) {
  return (
    <div className={cn("rounded-2xl border border-border bg-surface px-5 py-4 shadow-sm", className)}>
      <div className="text-sm font-medium text-muted-foreground">{label}</div>
      <div className="mt-1 font-heading text-4xl font-bold tracking-tight text-foreground tabular-nums">{value ?? "—"}</div>
      <div className="mt-1 text-sm text-muted-foreground">{sub}</div>
    </div>
  );
}

/** Judul section (`.dash-section-label` lama). */
export function DashboardSectionLabel({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "mt-8 mb-3 font-heading text-lg font-semibold text-foreground",
        className,
      )}
    >
      {children}
    </div>
  );
}

/** Kartu pembungkus satu chart (`.chart-card` lama). */
export function ChartCard({
  title,
  height,
  children,
}: {
  title: string;
  height: number;
  children: ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm">
      <div className="mb-3 text-base font-semibold text-foreground">{title}</div>
      <div style={{ height }}>{children}</div>
    </div>
  );
}
