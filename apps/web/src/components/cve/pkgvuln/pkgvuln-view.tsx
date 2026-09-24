"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { PkgVulnStats } from "@/lib/api/loose-types";
import { PackagesPanel } from "@/components/cve/pkgvuln/packages-panel";
import { VulnsPanel } from "@/components/cve/pkgvuln/vulns-panel";

/** Port `loadPkgVulnPanel()`/`pvSwitchSubview()`/`pvLoadStats()`
 * (`pkgvuln.js:49-81`) -- sub-view "Vulns" (default) dan "Packages" di
 * dalam `#cveview-pkgvuln`. */
export function PkgVulnView() {
  const [subview, setSubview] = useState<"vulns" | "packages">("vulns");

  const statsQuery = useQuery({
    queryKey: ["pkgvuln", "stats"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/pkgvuln/stats");
      if (error) throw error;
      return data as unknown as PkgVulnStats;
    },
  });

  const s = statsQuery.data;

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-4 border-b border-border pb-3 font-mono text-xs">
        <span>
          Packages <strong className="text-foreground">{s?.packages ?? 0}</strong>
        </span>
        <span>
          Vulns <strong className="text-foreground">{s?.total_vulns ?? 0}</strong>
        </span>
        <span className="text-destructive">Critical {s?.critical ?? 0}</span>
        <span className="text-warning">High {s?.high ?? 0}</span>
        <span className="text-primary">Medium {s?.medium ?? 0}</span>
        <span className="text-muted-foreground">Low {s?.low ?? 0}</span>
        <span>Unacked {s?.unacknowledged ?? 0}</span>
        <span className="text-destructive">KEV {s?.kev_count ?? 0}</span>
      </div>

      <div className="mb-3 flex gap-2">
        <Button size="sm" variant={subview === "vulns" ? "default" : "outline"} onClick={() => setSubview("vulns")}>
          Vulns
        </Button>
        <Button size="sm" variant={subview === "packages" ? "default" : "outline"} onClick={() => setSubview("packages")}>
          Packages
        </Button>
      </div>

      <div className={cn(subview !== "vulns" && "hidden")}>
        <VulnsPanel active={subview === "vulns"} />
      </div>
      <div className={cn(subview !== "packages" && "hidden")}>
        <PackagesPanel active={subview === "packages"} />
      </div>
    </div>
  );
}
