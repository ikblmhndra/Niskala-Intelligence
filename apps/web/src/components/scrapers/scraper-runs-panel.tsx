"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { SimplePager } from "@/components/pager";
import { RunStatusText } from "@/components/scrapers/status-badge";

const PAGE_SIZE = 10;

export function ScraperRunsPanel({ scraperId }: { scraperId: string }) {
  const [page, setPage] = useState(1);

  const query = useQuery({
    queryKey: ["scrapers", scraperId, "runs", page],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/scraper/{scraper_id}/runs", {
        params: { path: { scraper_id: scraperId }, query: { page, page_size: PAGE_SIZE } },
      });
      if (error) throw error;
      return data;
    },
  });

  const totalPages = Math.max(1, Math.ceil((query.data?.total ?? 0) / PAGE_SIZE));

  return (
    <div>
      {query.isPending && <p className="py-4 text-center text-xs text-muted-foreground">Loading…</p>}
      {query.isError && <p className="py-4 text-center text-xs text-destructive">Failed to load runs.</p>}
      {query.data && query.data.runs.length === 0 && (
        <p className="py-4 text-center text-xs text-muted-foreground">No runs recorded yet.</p>
      )}
      {query.data && query.data.runs.length > 0 && (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Started</TableHead>
              <TableHead>Trigger</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Found</TableHead>
              <TableHead>New</TableHead>
              <TableHead>Dropped</TableHead>
              <TableHead>Failed</TableHead>
              <TableHead>Duration</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {query.data.runs.map((r) => (
              <TableRow key={r.run_id}>
                <TableCell className="font-mono text-xs text-muted-foreground">
                  {r.started_at.replace("T", " ").split(".")[0]}
                </TableCell>
                <TableCell className="font-mono text-xs text-muted-foreground">{r.trigger}</TableCell>
                <TableCell>
                  <RunStatusText status={r.status} />
                </TableCell>
                <TableCell className="font-mono text-xs text-foreground">{r.items_found}</TableCell>
                <TableCell className="font-mono text-xs text-foreground">{r.items_new}</TableCell>
                <TableCell className="font-mono text-xs text-muted-foreground">{r.items_dropped}</TableCell>
                <TableCell className="font-mono text-xs text-destructive">{r.items_failed || ""}</TableCell>
                <TableCell className="font-mono text-xs text-muted-foreground">
                  {r.duration_ms != null ? `${r.duration_ms}ms` : "—"}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
      <div className="mt-2">
        <SimplePager page={page} totalPages={totalPages} onPageChange={setPage} />
      </div>
    </div>
  );
}
