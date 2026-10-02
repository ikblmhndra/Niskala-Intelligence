"use client";

import { useState } from "react";

import type { DiamondModel } from "@/lib/api/loose-types";
import { tint } from "@/lib/tint";

const TACTIC_ORDER = [
  "initial_access",
  "execution",
  "persistence",
  "privilege_escalation",
  "defense_evasion",
  "credential_access",
  "discovery",
  "lateral_movement",
  "collection",
  "exfiltration",
  "command_and_control",
  "impact",
  "other",
];

function Chips({ items, color, limit }: { items: string[] | undefined; color: string; limit?: number }) {
  if (!items || items.length === 0) return <span className="text-xs text-muted-foreground opacity-60">—</span>;
  const shown = items.slice(0, limit ?? 5);
  const more = items.length > (limit ?? 5) ? items.length - (limit ?? 5) : 0;
  return (
    <div className="flex flex-wrap gap-1">
      {shown.map((v, i) => (
        <span
          key={i}
          title={v}
          className="max-w-[120px] truncate rounded-full border px-1 py-0.5 font-mono text-xs"
          style={{ background: tint(color, 9), borderColor: tint(color, 27), color }}
        >
          {v}
        </span>
      ))}
      {more > 0 && <span className="text-xs text-muted-foreground">+{more}</span>}
    </div>
  );
}

/** Port `_renderDiamondModel()`/`_dmFullDetails()` (`clusters.js:429-577`)
 * -- 4 kuadran (Adversary/Infrastructure/Capability/Victim) + expand
 * detail penuh per-tactic MITRE. */
export function DiamondModelView({ clusterName, model }: { clusterName: string; model: DiamondModel }) {
  const [expanded, setExpanded] = useState(false);
  const adv = model.adversary;
  const inf = model.infrastructure;
  const cap = model.capability;
  const vic = model.victim;
  const meta = model.meta;

  const advItems = [...adv.threat_actors.slice(0, 3), ...adv.sponsoring_nations.map((n) => `${n}`), ...(adv.sophistication ? [`Soph: ${adv.sophistication}`] : [])];
  const allInfra = [...inf.domains, ...inf.ips, ...inf.urls];
  const allTechs = Object.values(cap.attack_techniques).flat();
  const capItems = [...allTechs.slice(0, 3), ...cap.malware.slice(0, 2).map((m) => `${m}`), ...cap.tools.slice(0, 1).map((t) => `🔧 ${t}`), ...cap.cve_exploited.slice(0, 2)];
  const vicItems = [...vic.industries, ...vic.countries, ...vic.organization_types.slice(0, 2)];

  const confColor = meta.confidence === "high" ? "var(--success)" : meta.confidence === "medium" ? "var(--severity-medium)" : "var(--muted-foreground)";

  return (
    <div className="mb-2.5">
      <div className="mb-2 flex flex-wrap items-center gap-2 font-mono text-xs tracking-[0.06em] text-muted-foreground uppercase">
        Diamond Model
        <span className="rounded-full border px-1.5 py-0.5 text-xs normal-case" style={{ background: tint(confColor, 9), borderColor: tint(confColor, 27), color: confColor }}>
          conf: {meta.confidence}
        </span>
        <span className="rounded-full border border-border bg-surface px-1.5 py-0.5 text-xs text-muted-foreground normal-case">{meta.direction}</span>
        <button type="button" onClick={() => setExpanded((e) => !e)} className="ml-auto rounded-full border border-border px-1.5 py-0.5 text-xs text-muted-foreground normal-case">
          {expanded ? "collapse" : "expand"}
        </button>
      </div>

      <div className="grid grid-cols-3 gap-0 px-2">
        <div />
        <div className="min-h-[64px] rounded-t-md border border-warning/25 bg-warning/6 p-2">
          <div className="mb-1 font-mono text-xs font-bold tracking-wide text-warning uppercase">▲ Adversary</div>
          <Chips items={advItems} color="var(--severity-high)" limit={4} />
        </div>
        <div />
        <div className="min-h-[72px] rounded-l-md border border-tag-violet/30 border-r-0 bg-tag-violet/8 p-2">
          <div className="mb-1 font-mono text-xs font-bold tracking-wide text-tag-violet uppercase">◀ Capability</div>
          <Chips items={capItems} color="var(--tag-violet)" limit={4} />
        </div>
        <div className="flex min-h-[72px] items-center justify-center border border-border bg-surface p-1.5 text-center">
          <span className="font-mono text-xs break-words text-muted-foreground">{clusterName.slice(0, 40)}</span>
        </div>
        <div className="min-h-[72px] rounded-r-md border border-primary/25 border-l-0 bg-primary/6 p-2">
          <div className="mb-1 font-mono text-xs font-bold tracking-wide text-primary uppercase">▶ Infrastructure</div>
          <Chips items={allInfra} color="var(--info)" limit={4} />
        </div>
        <div />
        <div className="min-h-[64px] rounded-b-md border border-success/25 border-t-0 bg-success/6 p-2">
          <div className="mb-1 font-mono text-xs font-bold tracking-wide text-success uppercase">▼ Victim</div>
          <Chips items={vicItems} color="var(--success)" limit={4} />
        </div>
        <div />
      </div>

      {expanded && (
        <div className="mt-2 grid grid-cols-2 gap-3 rounded-2xl border border-border bg-surface shadow-sm2 p-2">
          <div>
            <div className="mb-1.5 text-xs font-bold text-warning">Adversary</div>
            <FullSection title="Threat Actors" color="var(--severity-high)" items={adv.threat_actors} />
            <FullSection title="Actor Types" color="var(--severity-high)" items={adv.actor_types} />
            <FullSection title="Sponsoring Nations" color="var(--severity-high)" items={adv.sponsoring_nations} />
            {adv.sophistication && (
              <div className="font-mono text-xs text-muted-foreground">
                Sophistication: <span className="text-warning">{adv.sophistication}</span>
              </div>
            )}
          </div>
          <div>
            <div className="mb-1.5 text-xs font-bold text-primary">Infrastructure</div>
            <FullSection title="Domains" color="var(--info)" items={inf.domains} />
            <FullSection title="IPs" color="var(--info)" items={inf.ips} />
            <FullSection title="URLs" color="var(--info)" items={inf.urls} />
          </div>
          <div>
            <div className="mb-1.5 text-xs font-bold text-tag-violet">Capability</div>
            {TACTIC_ORDER.map((tactic) => {
              const techs = cap.attack_techniques[tactic];
              if (!techs || techs.length === 0) return null;
              return <FullSection key={tactic} title={tactic.replace(/_/g, " ")} color="var(--tag-violet)" items={techs} />;
            })}
            <FullSection title="Malware" color="var(--tag-violet)" items={cap.malware} />
            <FullSection title="Tools" color="var(--tag-violet)" items={cap.tools} />
            <FullSection title="CVEs Exploited" color="var(--tag-violet)" items={cap.cve_exploited} />
          </div>
          <div>
            <div className="mb-1.5 text-xs font-bold text-success">Victim</div>
            <FullSection title="Industries" color="var(--success)" items={vic.industries} />
            <FullSection title="Countries" color="var(--success)" items={vic.countries} />
            <FullSection title="Org Types" color="var(--success)" items={vic.organization_types} />
          </div>
        </div>
      )}
    </div>
  );
}

function FullSection({ title, color, items }: { title: string; color: string; items: string[] }) {
  if (!items || items.length === 0) return null;
  return (
    <div className="mb-2">
      <div className="mb-1 font-mono text-xs tracking-wide text-muted-foreground uppercase">{title}</div>
      <div className="flex flex-wrap gap-1">
        {items.map((v, i) => (
          <span key={i} className="rounded-full border px-1.5 py-0.5 font-mono text-xs" style={{ background: tint(color, 9), borderColor: tint(color, 27), color }}>
            {v}
          </span>
        ))}
      </div>
    </div>
  );
}
