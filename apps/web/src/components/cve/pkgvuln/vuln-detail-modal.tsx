"use client";

import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { epssColorClass, severityColorClass } from "@/lib/cve/format";
import type { components } from "@/lib/api/schema";

type PackageVulnOut = components["schemas"]["PackageVulnOut"];

interface VulnDetailModalProps {
  vuln: PackageVulnOut | null;
  onClose: () => void;
}

/** Port `_pvShowVulnFallback()` (`pkgvuln.js:565-620`ish) -- cross-link
 * ke modal CVE tab (`pvShowVulnDetail`'s `openCveModal` path) SENGAJA
 * gak diporting: butuh fetch tambahan (`GET /api/cve?search=`) cuma buat
 * kemungkinan-kecil match, sementara modal fallback ini SUDAH nampilin
 * semua data riil yang ada. Dicatat sebagai gap kecil di PROGRESS.md. */
export function VulnDetailModal({ vuln, onClose }: VulnDetailModalProps) {
  if (!vuln) return null;

  return (
    <Dialog open={vuln !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[80vh] w-full max-w-lg overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="font-mono">{vuln.advisory_id}</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 text-xs">
          <div className="flex flex-wrap items-center gap-2">
            <span className={cn("font-semibold", severityColorClass(vuln.adjusted_severity || vuln.severity))}>
              {vuln.adjusted_severity || vuln.severity}
            </span>
            {vuln.cvss_score != null && <span className="font-mono">CVSS {vuln.cvss_score.toFixed(1)}</span>}
            {vuln.kev && <Badge variant="destructive" className="text-xs">KEV</Badge>}
            {vuln.epss_score != null && (
              <Badge variant="outline" className={cn("text-xs", epssColorClass(vuln.epss_score))}>
                EPSS {(vuln.epss_score * 100).toFixed(2)}%
                {vuln.epss_percentile != null ? ` · ${Math.round(vuln.epss_percentile * 100)}th pct` : ""}
              </Badge>
            )}
          </div>

          <Row label="Package">
            {vuln.package_name}
            {vuln.pinned_version ? `@${vuln.pinned_version}` : ""} ({vuln.ecosystem})
          </Row>
          {vuln.aliases.length > 0 && <Row label="Aliases">{vuln.aliases.join(", ")}</Row>}
          <Row label="Summary">{vuln.summary || "—"}</Row>
          {vuln.details && <Row label="Description">{vuln.details}</Row>}
          <div className="grid grid-cols-2 gap-2">
            <Row label="Published">{vuln.published?.slice(0, 10) || "—"}</Row>
            <Row label="Modified">{vuln.modified?.slice(0, 10) || "—"}</Row>
            <Row label="Fixed In">{vuln.fixed_version || "—"}</Row>
            <Row label="Source">{vuln.source}</Row>
          </div>
          {vuln.affected_version_ranges.length > 0 && (
            <Row label="Affected Ranges">
              <span className="font-mono">{vuln.affected_version_ranges.join(", ")}</span>
            </Row>
          )}
          {vuln.references.length > 0 && (
            <Row label="References">
              <div className="space-y-1">
                {vuln.references.map((r, i) => (
                  <a key={i} href={r} target="_blank" rel="noopener noreferrer" className="block truncate text-primary">
                    {r}
                  </a>
                ))}
              </div>
            </Row>
          )}
          {vuln.acknowledged && (
            <Row label="Acknowledged">
              {vuln.ack_by || "—"} on {vuln.ack_date?.slice(0, 10) || "—"}
            </Row>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="font-mono text-xs text-muted-foreground uppercase">{label}</div>
      <div className="mt-0.5 leading-relaxed">{children}</div>
    </div>
  );
}
