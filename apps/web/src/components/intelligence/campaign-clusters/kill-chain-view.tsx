import type { KillChain } from "@/lib/api/loose-types";

const LABEL_COLOR: Record<string, string> = { full_chain: "#ff6b6b", partial_chain: "#ffaa00", limited: "#888" };
const RISK_COLOR: Record<string, string> = { critical: "#ff6b6b", high: "#ffaa00", medium: "#cccc00", low: "#888" };

/** Port bagian Kill Chain di `_renderCampaignExpanded()` (`clusters.js:334-378`)
 * -- 12 fase MITRE kill-chain, segmen warna per-fase covered/enggak. */
export function KillChainView({ killChain: kc }: { killChain: KillChain }) {
  const labelColor = LABEL_COLOR[kc.completeness_label] ?? LABEL_COLOR.limited;
  const riskColor = RISK_COLOR[kc.operational_risk] ?? RISK_COLOR.low;
  const covered = kc.chain_visualization.filter((p) => p.covered && p.techniques.length > 0);

  return (
    <div className="mb-2.5">
      <div className="mb-1.5 flex flex-wrap items-center gap-2 font-mono text-[10px] tracking-[0.06em] text-muted-foreground uppercase">
        Kill Chain Coverage
        <span className="rounded-sm border px-1.5 py-0.5 text-[9px] font-bold normal-case" style={{ background: `${labelColor}22`, borderColor: `${labelColor}55`, color: labelColor }}>
          {kc.completeness_score}% — {kc.completeness_label.replace(/_/g, " ")}
        </span>
        <span className="text-[9px] normal-case" style={{ color: riskColor }}>
          Risk: {kc.operational_risk}
        </span>
      </div>
      <div className="mb-1.5 flex gap-0.5 px-0.5">
        {kc.chain_visualization.map((p) => (
          <div
            key={p.phase}
            title={`${p.phase.replace(/_/g, " ")}${p.techniques.length ? "\n" + p.techniques.join("\n") : ""}`}
            className="h-3 flex-1 rounded-sm border"
            style={{ background: p.covered ? labelColor : "rgba(100,100,100,0.2)", borderColor: p.covered ? labelColor : "rgba(100,100,100,0.3)", opacity: p.covered ? 0.85 : 0.3 }}
          />
        ))}
      </div>
      <div className="mb-2 flex gap-0.5 px-0.5">
        {kc.chain_visualization.map((p) => (
          <div key={p.phase} title={p.phase.replace(/_/g, " ")} className="flex-1 truncate text-center font-mono text-[7px] text-muted-foreground">
            {p.phase.split("_")[0]}
          </div>
        ))}
      </div>
      {covered.length > 0 && (
        <div className="rounded-md border border-border bg-surface2 p-2">
          {covered.map((p) => (
            <div key={p.phase} className="flex items-start gap-1.5 py-0.5">
              <span className="w-[100px] flex-shrink-0 pt-px font-mono text-[9px] text-muted-foreground">{p.phase.replace(/_/g, " ")}</span>
              <div className="flex flex-wrap gap-1">
                {p.techniques.map((t, i) => (
                  <span key={i} className="rounded-sm border border-[#a78bdb]/30 bg-[#a78bdb]/15 px-1 py-0.5 font-mono text-[8px] text-[#a78bdb]">
                    {t}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
