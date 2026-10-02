import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

interface StatBoxProps {
  label: string;
  value: number | string | undefined;
  sub: ReactNode;
  className?: string;
  /** Deret angka untuk sparkline kecil di kanan nilai. */
  spark?: number[];
}

/** Port `.dash-stat-box` dari `newsroom.html`/`custom.css` lama. */
export function StatBox({ label, value, sub, className, spark }: StatBoxProps) {
  return (
    <div className={cn("rounded-2xl border border-border bg-surface px-5 py-4 shadow-sm", className)}>
      <div className="text-sm font-medium text-muted-foreground">{label}</div>
      <div className="mt-1 flex items-end justify-between gap-3">
        <div className="font-heading text-4xl font-bold tracking-tight text-foreground tabular-nums">{value ?? "—"}</div>
        {spark && spark.length > 1 && <Sparkline data={spark} />}
      </div>
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

/** Kartu untuk konten berukuran bebas (peta, daftar) -- tanpa tinggi tetap. */
export function MapCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm">
      <div className="mb-3 text-base font-semibold text-foreground">{title}</div>
      {children}
    </div>
  );
}

function Sparkline({ data }: { data: number[] }) {
  const W = 120;
  const H = 36;
  const max = Math.max(...data);
  const min = Math.min(...data);
  const span = Math.max(1, max - min);
  const pts = data
    .map((v, i) => `${((i / (data.length - 1)) * W).toFixed(1)},${(H - 4 - ((v - min) / span) * (H - 8)).toFixed(1)}`)
    .join(" ");
  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} aria-hidden className="shrink-0 text-info">
      <polyline points={pts} fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
