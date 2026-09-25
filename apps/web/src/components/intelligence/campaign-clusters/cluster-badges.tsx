const SEVERITY_STYLE: Record<string, string> = {
  critical: "bg-destructive/18 border-destructive/50 text-destructive",
  high: "bg-warning/15 border-warning/45 text-warning",
  medium: "bg-[#cccc00]/12 border-[#cccc00]/40 text-[#cccc00]",
  low: "bg-muted-foreground/15 border-muted-foreground/35 text-muted-foreground",
};

export function SeverityBadge({ label, score }: { label: string; score: number | null }) {
  const cls = SEVERITY_STYLE[label] ?? SEVERITY_STYLE.low;
  return (
    <span className={`ml-1 inline-block rounded-sm border px-1.5 py-0.5 font-mono text-[9px] font-bold ${cls}`}>
      {label.toUpperCase()} {score ?? ""}
    </span>
  );
}

export function VelocityBadge({ label, articlesPerDay }: { label: string; articlesPerDay: number }) {
  if (label === "surging") {
    return (
      <span className="ml-1 inline-flex items-center gap-1">
        <span className="inline-block size-[7px] animate-pulse rounded-full bg-destructive" />
        <span className="font-mono text-[9px] font-bold tracking-wide text-destructive">SURGING</span>
      </span>
    );
  }
  if (label === "active") {
    return (
      <span className="ml-1 inline-flex items-center gap-1">
        <span className="inline-block size-[7px] rounded-full bg-warning" />
        <span className="font-mono text-[9px] font-bold tracking-wide text-warning">ACTIVE</span>
      </span>
    );
  }
  const color = label === "moderate" ? "bg-[#cccc00]" : "bg-muted-foreground/60";
  return (
    <span className="ml-1 inline-flex items-center" title={`${label} — ${articlesPerDay.toFixed(1)}/day`}>
      <span className={`inline-block size-[7px] rounded-full ${color}`} />
    </span>
  );
}

const TREND_ARROW: Record<string, string> = { growing: "↗", stable: "→", declining: "↘", dormant: "↓" };
const TREND_COLOR: Record<string, string> = {
  growing: "text-destructive",
  stable: "text-[#cccc00]",
  declining: "text-success",
  dormant: "text-muted-foreground",
};

export function TrendArrow({ direction, growthRate }: { direction: string; growthRate: number | null }) {
  const gr = growthRate != null ? ` ${growthRate > 0 ? "+" : ""}${growthRate}%` : "";
  return (
    <span className={`ml-1 text-xs ${TREND_COLOR[direction] ?? "text-muted-foreground"}`} title={`Trend: ${direction}${gr}`}>
      {TREND_ARROW[direction] ?? "→"}
    </span>
  );
}

const KC_STYLE: Record<string, string> = {
  full_chain: "bg-destructive/15 border-destructive/40 text-destructive",
  partial_chain: "bg-warning/12 border-warning/35 text-warning",
  limited: "bg-muted-foreground/12 border-muted-foreground/30 text-muted-foreground",
};

export function KillChainBadge({ label, score }: { label: string; score: number }) {
  const cls = KC_STYLE[label] ?? KC_STYLE.limited;
  return <span className={`ml-1 inline-block rounded-sm border px-1.5 py-0.5 font-mono text-[9px] font-bold ${cls}`}>{score}%</span>;
}

const LINK_TYPE_STYLE: Record<string, string> = {
  same_actor: "bg-destructive/12 border-destructive/40 text-destructive",
  shared_infra: "bg-warning/12 border-warning/35 text-warning",
  similar_ttp: "bg-[#a78bdb]/15 border-[#a78bdb]/35 text-[#a78bdb]",
  related: "bg-muted-foreground/12 border-muted-foreground/30 text-muted-foreground",
};
const LINK_TYPE_LABEL: Record<string, string> = {
  same_actor: "Same Actor",
  shared_infra: "Shared Infra",
  similar_ttp: "Similar TTP",
  related: "Related",
};

export function LinkTypeBadge({ type }: { type: string }) {
  const cls = LINK_TYPE_STYLE[type] ?? LINK_TYPE_STYLE.related;
  return <span className={`inline-block flex-shrink-0 rounded-sm border px-1.5 py-0.5 font-mono text-[9px] ${cls}`}>{LINK_TYPE_LABEL[type] ?? type}</span>;
}

const CVE_PRIO_STYLE: Record<string, string> = {
  critical_patch: "border-destructive/60 bg-destructive/8",
  high_priority: "border-warning/60 bg-warning/8",
  medium: "border-[#cccc00]/50 bg-[#cccc00]/8",
};

export function CvePriorityChip({ cve, onClick }: { cve: { cve_id: string; cvss_score: number | null; priority_label: string | null; patch_urgency: string | null; in_tech_stack: boolean }; onClick: () => void }) {
  const cls = CVE_PRIO_STYLE[cve.priority_label ?? ""] ?? "border-success/40 bg-success/6";
  return (
    <button
      type="button"
      onClick={onClick}
      title={`${cve.priority_label ?? ""}${cve.patch_urgency ? ` — patch: ${cve.patch_urgency}` : ""}`}
      className={`inline-flex items-center gap-0.5 rounded-sm border px-1.5 py-0.5 font-mono text-[9px] text-foreground ${cls}`}
    >
      {cve.in_tech_stack && <span title="In your tech stack" className="text-[#ffcc00]">★</span>}
      {cve.cve_id}
      {cve.cvss_score != null && <span className="opacity-75">{cve.cvss_score}</span>}
    </button>
  );
}
