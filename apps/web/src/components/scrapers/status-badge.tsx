const STATUS_STYLE: Record<string, string> = {
  ok: "bg-primary/12 border-primary/40 text-primary",
  disabled: "bg-muted-foreground/12 border-muted-foreground/35 text-muted-foreground",
  stale: "bg-[#cccc00]/12 border-[#cccc00]/40 text-[#cccc00]",
  dead: "bg-destructive/18 border-destructive/50 text-destructive",
  degraded: "bg-warning/15 border-warning/45 text-warning",
  zero_yield: "bg-[#cccc00]/12 border-[#cccc00]/40 text-[#cccc00]",
};

/** Pill status kesehatan scraper -- `cti_scraper.health.HealthStatus`
 * (Fase 9 H3): ok/disabled/stale/dead/degraded/zero_yield. */
export function StatusBadge({ status }: { status: string }) {
  const cls = STATUS_STYLE[status] ?? STATUS_STYLE.stale;
  return (
    <span className={`inline-block rounded-sm border px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase ${cls}`}>
      {status.replace("_", " ")}
    </span>
  );
}

const RUN_STATUS_STYLE: Record<string, string> = {
  ok: "text-primary",
  empty: "text-muted-foreground",
  partial: "text-warning",
  fetch_error: "text-destructive",
  parse_error: "text-destructive",
  rate_limited: "text-warning",
  timeout: "text-destructive",
  backpressure: "text-warning",
  disabled: "text-muted-foreground",
  running: "text-[#cccc00]",
};

/** Warna teks status run (`ScraperRun.status`) -- BUKAN pill kayak
 * `StatusBadge`, dipakai inline di tabel runs (lebih banyak baris, pill
 * penuh kebesaran). */
export function RunStatusText({ status }: { status: string }) {
  return <span className={`font-mono text-[10px] ${RUN_STATUS_STYLE[status] ?? ""}`}>{status}</span>;
}
