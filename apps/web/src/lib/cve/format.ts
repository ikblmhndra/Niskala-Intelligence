import type { components } from "@/lib/api/schema";

type CveOut = components["schemas"]["CveOut"];

/**
 * Port `_SEV_TIER`/`_TIER_SEV`/`_SEV_COLOR`/`_effectiveSeverity()`
 * (`cve.js:133-145`). Colors re-mapped ke token Tailwind (keputusan
 * re-theme Fase 8), bukan CSS var mentah punya legacy.
 */
const SEV_TIER: Record<string, number> = { LOW: 0, MEDIUM: 1, HIGH: 2, CRITICAL: 3 };
const TIER_SEV = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];

export const SEVERITY_COLOR_CLASS: Record<string, string> = {
  CRITICAL: "text-destructive",
  HIGH: "text-warning",
  MEDIUM: "text-primary",
  LOW: "text-success",
};

export function severityColorClass(sev: string): string {
  return SEVERITY_COLOR_CLASS[sev.toUpperCase()] ?? "text-muted-foreground";
}

/**
 * PoC-nya cuma pernah `poc_type` = `"poc"` | `"exploit"` (cek
 * `scrapers/src/cti_scrapers/feeds/github_poc_monitor.py::_poc_type()`)
 * -- cabang `metasploit_module` di legacy gak pernah kejadian, gak
 * ikut di-port.
 */
export function effectiveSeverity(c: CveOut): { base: string; effective: string; escalated: boolean } {
  const base = (c.cve_severity || "").toUpperCase();
  if (!c.poc_available) return { base, effective: base, escalated: false };
  const hasWeaponized = (c.pocs || []).some((p) => p.poc_type === "exploit");
  if (!hasWeaponized) return { base, effective: base, escalated: false };
  const tier = SEV_TIER[base] ?? -1;
  if (tier < 0 || tier >= 3) return { base, effective: base, escalated: false };
  return { base, effective: TIER_SEV[tier + 1], escalated: true };
}

/**
 * `affected` berubah shape dari dict Mongo-era (`{product: [ranges]}`)
 * jadi flat string `"Product: constraint"` di skema baru (lihat
 * `scrapers/src/cti_scrapers/feeds/new_cve.py:222`) -- `_renderAffected`/
 * `_renderAffectedFull` lama gak bisa dipakai apa adanya, parsing baru
 * di bawah split tiap entry di `": "` pertama.
 */
export interface ParsedAffected {
  product: string;
  constraint: string;
}

export function parseAffected(affected: string[]): ParsedAffected[] {
  return affected.map((entry) => {
    const idx = entry.indexOf(": ");
    if (idx === -1) return { product: entry, constraint: "" };
    return { product: entry.slice(0, idx), constraint: entry.slice(idx + 2) };
  });
}

export function epssColorClass(score: number): string {
  if (score >= 0.5) return "text-destructive";
  if (score >= 0.1) return "text-warning";
  return "text-primary";
}

export function newsMentionUrl(m: Record<string, string>): string {
  return m.url ?? "";
}

export function newsMentionTitle(m: Record<string, string>): string {
  return m.title ?? "";
}
