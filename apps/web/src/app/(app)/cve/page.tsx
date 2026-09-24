"use client";

import { useState } from "react";

import { cn } from "@/lib/utils";
import { CveCoreView } from "@/components/cve/cve-core-view";
import { TechStackPanel } from "@/components/cve/techstack-panel";
import { PkgVulnView } from "@/components/cve/pkgvuln/pkgvuln-view";

const VIEWS = [
  { id: "cves", label: "CVE Tracker" },
  { id: "pkgvuln", label: "Package Vulnerabilities" },
] as const;
type View = (typeof VIEWS)[number]["id"];

const CVE_SUBVIEWS = [
  { id: "cves", label: "CVEs" },
  { id: "techstack", label: "Tech Stack" },
] as const;
type CveSubview = (typeof CVE_SUBVIEWS)[number]["id"];

/**
 * Port `tab_cvetracker.html`+`cve.js`+`techstack.js`+`pkgvuln.js`.
 * Area terbesar tunggal Fase 8 (Grup E) -- 2 level switch: view
 * (CVEs|Package Vulnerabilities, `cveSwitchView`) dan, di dalam CVEs,
 * sub-view (CVEs|Tech Stack, `cveSwitchTSVSubview`). Backend (ticket
 * workflow, 3 lookup eksternal, techstack, pkgvuln) SUDAH lengkap
 * diporting sejak Fase 7 -- ini murni build frontend.
 */
export default function CveTrackerPage() {
  const [view, setView] = useState<View>("cves");
  const [subview, setSubview] = useState<CveSubview>("cves");

  return (
    <div>
      <div className="mb-4 flex gap-1.5 border-b border-border pb-3">
        {VIEWS.map((v) => (
          <button
            key={v.id}
            onClick={() => setView(v.id)}
            className={cn(
              "rounded-md border px-3.5 py-1.5 font-mono text-xs tracking-wide transition-colors",
              view === v.id
                ? "border-primary/40 bg-primary/10 text-primary"
                : "border-border text-muted-foreground hover:bg-accent",
            )}
          >
            {v.label}
          </button>
        ))}
      </div>

      {view === "cves" ? (
        <div>
          <div className="mb-3 flex gap-1.5">
            {CVE_SUBVIEWS.map((s) => (
              <button
                key={s.id}
                onClick={() => setSubview(s.id)}
                className={cn(
                  "rounded-md border px-3 py-1 font-mono text-[11px] tracking-wide transition-colors",
                  subview === s.id
                    ? "border-primary/40 bg-primary/10 text-primary"
                    : "border-border text-muted-foreground hover:bg-accent",
                )}
              >
                {s.label}
              </button>
            ))}
          </div>
          {subview === "cves" ? <CveCoreView /> : <TechStackPanel />}
        </div>
      ) : (
        <PkgVulnView />
      )}
    </div>
  );
}
