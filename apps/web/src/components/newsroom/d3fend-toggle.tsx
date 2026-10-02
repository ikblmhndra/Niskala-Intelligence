"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import { Button } from "@/components/ui/button";

interface D3fendMeasure {
  id: string;
  name: string;
  tactic: string;
  artifact: string;
  url: string;
}

/** Port `toggleD3fend()`/`_fetchD3fend()`/`_renderD3fend()` (`ttp.js`) --
 * baris expand inline di tabel TTP modal artikel. `openTtpDrill()` (drill
 * artikel per TTP dari MITRE heatmap) BUKAN bagian ini -- itu punya
 * `/intelligence` heatmap, Grup G. */
export function D3fendToggle({ ttpId }: { ttpId: string }) {
  const [open, setOpen] = useState(false);
  const query = useQuery({
    queryKey: ["mitre", "d3fend", ttpId],
    queryFn: async () => {
      const { data, response } = await api.GET("/api/mitre/d3fend/{technique_id}", {
        params: { path: { technique_id: ttpId } },
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return (data as { countermeasures?: D3fendMeasure[] } | undefined)?.countermeasures ?? [];
    },
    enabled: open,
    staleTime: Infinity,
  });

  return (
    <>
      <Button size="sm" variant="outline" onClick={() => setOpen((o) => !o)}>
        🛡 Defenses
      </Button>
      {open && (
        <div className="mt-1.5 rounded-md border border-border bg-muted/30 p-2">
          {query.isPending && <span className="text-xs text-muted-foreground">Loading…</span>}
          {query.isError && <span className="text-xs text-destructive">Failed to load.</span>}
          {query.data && query.data.length === 0 && (
            <span className="text-xs text-muted-foreground">
              No D3FEND countermeasures mapped for this technique.
            </span>
          )}
          {query.data && query.data.length > 0 && (
            <div>
              <div className="mb-1.5 font-mono text-xs tracking-[0.08em] text-muted-foreground uppercase">
                D3FEND Countermeasures
              </div>
              <div className="flex flex-wrap gap-1.5">
                {query.data.map((m) => (
                  <a
                    key={m.id}
                    href={m.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    title={m.artifact}
                    className="rounded border border-secondary/30 bg-secondary/10 px-2 py-0.5 font-mono text-xs text-secondary no-underline"
                  >
                    {m.name}
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </>
  );
}
