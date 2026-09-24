"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api } from "@/lib/api/client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { SimplePager } from "@/components/pager";
import { PanelError, PanelLoading } from "@/components/newsroom/panel-shell";
import { ConfirmDialog } from "@/components/confirm-dialog";
import type { TechStackActionResult, TechStackSuccessFlag } from "@/lib/api/loose-types";

const PAGE_SIZE = 20;
const EXPOSURES = ["internal", "public", "both"];
const HOSTINGS = ["on_prem", "cloud", "saas"];

function selectClass() {
  return "h-6 rounded border border-input bg-transparent px-1.5 font-mono text-[10px] outline-none";
}

/** Port sub-tab Tech Stack (`techstack.js`) di dalam CVE tab
 * (`#cveview-techstack`). Tombol "↺ Historical backfill"/"↺ Backfill
 * CVEs" legacy TIDAK diport -- endpoint-nya sengaja belum ada di
 * `routers/techstack.py` (nulis ke `cve_tracker`, nyusul bareng gap lain
 * yang udah diselesaikan router `cve.py`, tapi backfill-nya sendiri
 * belum). `DELETE` juga gak cascade-delete CVE / balikin `cves_deleted`
 * (beda dari legacy), copy disesuaikan. */
export function TechStackPanel() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [name, setName] = useState("");
  const [exposure, setExposure] = useState("internal");
  const [hosting, setHosting] = useState("on_prem");
  const [adding, setAdding] = useState(false);
  const [removeTarget, setRemoveTarget] = useState<{ id: number; name: string } | null>(null);

  const listQuery = useQuery({
    queryKey: ["techstack", "list", search, page],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/techstack", {
        params: { query: { page, page_size: PAGE_SIZE, sort_by: "name", sort_dir: "asc", search: search || undefined } },
      });
      if (error) throw error;
      return data;
    },
  });

  function invalidate() {
    void queryClient.invalidateQueries({ queryKey: ["techstack", "list"] });
    void queryClient.invalidateQueries({ queryKey: ["cve", "tech-list"] });
  }

  async function addTech() {
    if (!name.trim()) return;
    setAdding(true);
    try {
      const { data, error } = await api.POST("/api/techstack", {
        body: { name: name.trim(), exposure, hosting_type: hosting },
      });
      if (error) throw new Error(JSON.stringify(error));
      const d = data as unknown as TechStackActionResult;
      if (!d.success) {
        toast.error(d.reason || `${name} already exists`);
        return;
      }
      setName("");
      invalidate();
    } catch (e) {
      toast.error(`Add failed: ${(e as Error).message}`);
    } finally {
      setAdding(false);
    }
  }

  async function removeTech(id: number) {
    const { data, error } = await api.DELETE("/api/techstack/{tech_id}", { params: { path: { tech_id: id } } });
    if (error) {
      toast.error("Remove failed");
      return;
    }
    const d = data as unknown as TechStackSuccessFlag;
    if (d.success) toast.success("Removed.");
    invalidate();
  }

  async function changeExposure(id: number, value: string) {
    const { error } = await api.PATCH("/api/techstack/{tech_id}/exposure", {
      params: { path: { tech_id: id } },
      body: { exposure: value },
    });
    if (error) {
      toast.error("Exposure update failed");
      invalidate();
      return;
    }
    invalidate();
  }

  async function changeHosting(id: number, value: string) {
    const { error } = await api.PATCH("/api/techstack/{tech_id}/hosting", {
      params: { path: { tech_id: id } },
      body: { hosting_type: value },
    });
    if (error) {
      toast.error("Hosting update failed");
      invalidate();
      return;
    }
    invalidate();
  }

  const total = listQuery.data?.total ?? 0;
  const totalPages = Math.ceil(total / PAGE_SIZE) || 1;

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-end gap-2 border-b border-border pb-3">
        <div className="flex flex-col gap-1">
          <Label className="font-mono text-[9px] text-muted-foreground uppercase">Search</Label>
          <Input
            placeholder="Tech name…"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="w-44 font-mono text-xs"
          />
        </div>
        <div className="flex flex-col gap-1">
          <Label className="font-mono text-[9px] text-muted-foreground uppercase">Name</Label>
          <Input placeholder="e.g. WordPress" value={name} onChange={(e) => setName(e.target.value)} className="w-44 font-mono text-xs" />
        </div>
        <div className="flex flex-col gap-1">
          <Label className="font-mono text-[9px] text-muted-foreground uppercase">Exposure</Label>
          <select value={exposure} onChange={(e) => setExposure(e.target.value)} className={selectClass()}>
            {EXPOSURES.map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <Label className="font-mono text-[9px] text-muted-foreground uppercase">Hosting</Label>
          <select value={hosting} onChange={(e) => setHosting(e.target.value)} className={selectClass()}>
            {HOSTINGS.map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
        </div>
        <Button size="sm" disabled={!name.trim() || adding} onClick={() => void addTech()}>
          + Add
        </Button>
      </div>

      {listQuery.isPending && <PanelLoading />}
      {listQuery.isError && <PanelError />}
      {listQuery.data && (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Added Date</TableHead>
                <TableHead>Source</TableHead>
                <TableHead>Exposure</TableHead>
                <TableHead>Hosting</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {listQuery.data.items.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="py-8 text-center text-xs text-muted-foreground">
                    No tech stack entries.
                  </TableCell>
                </TableRow>
              )}
              {listQuery.data.items.map((t) => (
                <TableRow key={t.id}>
                  <TableCell className="font-mono text-xs">{t.name}</TableCell>
                  <TableCell className="font-mono text-[11px] text-muted-foreground">{t.added_date?.slice(0, 10) || "—"}</TableCell>
                  <TableCell>
                    <Badge variant="outline" className="text-[10px]">
                      {t.source || "manual"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <select
                      value={t.exposure}
                      onChange={(e) => void changeExposure(t.id, e.target.value)}
                      className={selectClass()}
                    >
                      {EXPOSURES.map((v) => (
                        <option key={v} value={v}>
                          {v}
                        </option>
                      ))}
                    </select>
                  </TableCell>
                  <TableCell>
                    <select
                      value={t.hosting_type}
                      onChange={(e) => void changeHosting(t.id, e.target.value)}
                      className={selectClass()}
                    >
                      {HOSTINGS.map((v) => (
                        <option key={v} value={v}>
                          {v}
                        </option>
                      ))}
                    </select>
                  </TableCell>
                  <TableCell>
                    <Button size="sm" variant="destructive" onClick={() => setRemoveTarget({ id: t.id, name: t.name })}>
                      Remove
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <div className="mt-3 flex justify-center">
            <SimplePager page={page} totalPages={totalPages} totalLabel={`${total} results`} onPageChange={setPage} />
          </div>
        </>
      )}

      <ConfirmDialog
        open={removeTarget !== null}
        onOpenChange={(open) => !open && setRemoveTarget(null)}
        title="Remove tech stack entry"
        description={`Remove "${removeTarget?.name}" from tech stack?`}
        confirmLabel="Remove"
        onConfirm={() => removeTarget && void removeTech(removeTarget.id)}
      />
    </div>
  );
}
