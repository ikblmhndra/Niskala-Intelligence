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
    <div className={cn("rounded-md border border-border bg-surface px-4 py-3", className)}>
      <div className="font-mono text-[10px] tracking-wide text-muted-foreground uppercase">
        {label}
      </div>
      <div className="font-heading text-2xl text-foreground">{value ?? "—"}</div>
      <div className="mt-0.5 text-xs text-muted-foreground">{sub}</div>
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
        "mt-6 mb-2 border-b border-border pb-1 font-mono text-[10px] tracking-[0.12em] text-muted-foreground uppercase",
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
    <div className="rounded-md border border-border bg-surface p-3">
      <div className="mb-2 font-mono text-xs text-muted-foreground">{title}</div>
      <div style={{ height }}>{children}</div>
    </div>
  );
}
