"use client";

import { RefreshCwIcon } from "lucide-react";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import type { RecapDoc, RecapListItem } from "@/lib/api/loose-types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { RecapHistory } from "@/components/recap/recap-history";
import { RecapView } from "@/components/recap/recap-view";

function yesterdayIso(): string {
  return new Date(Date.now() - 86400000).toISOString().slice(0, 10);
}

function useRecapHistory() {
  return useQuery({
    queryKey: ["recap", "list"],
    queryFn: async () => {
      const { data, response } = await api.GET("/api/recap/list", {
        params: { query: { limit: 60 } },
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return (data as { recaps?: RecapListItem[] } | undefined)?.recaps ?? [];
    },
  });
}

function useRecapDoc(date: string) {
  return useQuery({
    queryKey: ["recap", "doc", date],
    queryFn: async () => {
      if (!date) {
        const { data, response } = await api.GET("/api/recap/latest");
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return (data as { recap: RecapDoc | null } | undefined)?.recap ?? null;
      }
      const { data, response } = await api.GET("/api/recap/{date}", {
        params: { path: { date } },
      });
      if (response.status === 404) return null;
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return (data as { recap: RecapDoc } | undefined)?.recap ?? null;
    },
  });
}

function useGenerateRecap() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ date, force }: { date: string; force: boolean }) => {
      const { data, response } = await api.POST("/api/recap/generate", {
        params: { query: { date: date || undefined, force } },
      });
      if (!response.ok) {
        const text = await response.text().catch(() => "");
        throw new Error(`HTTP ${response.status}${text ? `: ${text.slice(0, 200)}` : ""}`);
      }
      return (data as { recap: RecapDoc } | undefined)?.recap ?? null;
    },
    onSuccess: (recap, variables) => {
      if (recap) {
        queryClient.setQueryData(["recap", "doc", variables.date], recap);
      }
      void queryClient.invalidateQueries({ queryKey: ["recap", "list"] });
    },
  });
}

/**
 * Port `legacy/static/js/newsroom/recap.js` + `tab_recap.html`. Dua state
 * tanggal terpisah kayak lama: `inputDate` (nilai date-picker mentah) vs
 * `selectedDate` (tanggal yang beneran di-query) -- LOAD baru nge-sync
 * keduanya, generate baca `inputDate` langsung (independen dari yang lagi
 * ke-render), sama persis perilaku `recapLoad()`/`recapGenerate()` lama.
 */
export default function RecapPage() {
  const [inputDate, setInputDate] = useState(yesterdayIso);
  const [selectedDate, setSelectedDate] = useState(yesterdayIso);
  const [confirm, setConfirm] = useState<{ force: boolean } | null>(null);

  const history = useRecapHistory();
  const doc = useRecapDoc(selectedDate);
  const generate = useGenerateRecap();

  const dateLabel = inputDate || "yesterday";

  const status = useMemo(() => {
    if (generate.isPending) return { text: "Generating… this can take 10-30s", tone: "info" as const };
    if (generate.isError) return { text: (generate.error as Error).message, tone: "err" as const };
    if (generate.isSuccess) return { text: "Generated · saved", tone: "ok" as const };
    if (doc.isFetching) return { text: "Loading…", tone: "info" as const };
    if (doc.isError) return { text: (doc.error as Error).message, tone: "err" as const };
    if (doc.data === null) return { text: "No recap stored for that date", tone: "warn" as const };
    if (doc.data) return { text: "Loaded", tone: "ok" as const };
    return { text: "", tone: "info" as const };
  }, [generate.isPending, generate.isError, generate.isSuccess, generate.error, doc.isFetching, doc.isError, doc.error, doc.data]);

  const statusColor = {
    info: "text-muted-foreground",
    ok: "text-primary",
    err: "text-destructive",
    warn: "text-warning",
  }[status.tone];

  function handleSelectHistory(date: string) {
    setInputDate(date);
    setSelectedDate(date);
  }

  function handleConfirmGenerate() {
    if (!confirm) return;
    generate.mutate(
      { date: inputDate, force: confirm.force },
      { onSuccess: () => setSelectedDate(inputDate) },
    );
    setConfirm(null);
  }

  return (
    <div className="pb-10">
      <div className="mb-4 flex flex-wrap items-center gap-2.5 border-b border-border pb-3">
        <span className="text-sm font-semibold text-muted-foreground">
          Recap Date
        </span>
        <Input
          type="date"
          value={inputDate}
          onChange={(e) => setInputDate(e.target.value)}
          className="w-auto font-mono text-xs"
        />
        <Button size="sm" onClick={() => setSelectedDate(inputDate)}>
          Load
        </Button>
        <Button size="sm" variant="secondary" onClick={() => setConfirm({ force: false })}>
          ↻ Generate
        </Button>
        <Button size="sm" variant="outline" onClick={() => setConfirm({ force: true })}>
          <RefreshCwIcon aria-hidden /> Force Regen
        </Button>
        <span className={`ml-auto font-mono text-xs ${statusColor}`}>{status.text}</span>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[240px_1fr]">
        <div className="max-h-[calc(100vh-220px)] overflow-y-auto rounded-2xl border border-border bg-surface shadow-sm p-2.5">
          <div className="mb-2 border-b border-border pb-1.5 text-sm font-semibold text-muted-foreground">
            Recap History
          </div>
          {history.isPending && (
            <div className="space-y-1.5">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          )}
          {history.isError && <p className="p-1.5 text-xs text-destructive">Failed to load history.</p>}
          {history.data && (
            <RecapHistory items={history.data} selectedDate={selectedDate} onSelect={handleSelectHistory} />
          )}
        </div>

        <div className="min-h-[300px]">
          {doc.isPending && (
            <div className="space-y-2">
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-32 w-full" />
            </div>
          )}
          {doc.isError && <p className="text-sm text-destructive">{(doc.error as Error).message}</p>}
          {doc.data && <RecapView doc={doc.data} />}
          {doc.data === null && (
            <div className="rounded-md border border-dashed border-border px-6 py-8 text-center">
              <p className="mb-3 font-mono text-xs text-muted-foreground">
                No recap stored for <span className="font-medium text-foreground">{dateLabel}</span>.
              </p>
              <Button size="sm" onClick={() => setConfirm({ force: false })}>
                ↻ Generate Now
              </Button>
            </div>
          )}
        </div>
      </div>

      <ConfirmDialog
        open={confirm !== null}
        onOpenChange={(open) => !open && setConfirm(null)}
        title="Generate Daily Recap"
        description={`Generate recap for ${dateLabel}? This calls the LLM and may take 10–30 seconds.`}
        warning={confirm?.force ? "FORCE REGEN will overwrite the existing recap for this date." : undefined}
        confirmLabel={confirm?.force ? "Force Regen" : "Generate"}
        onConfirm={handleConfirmGenerate}
      />
    </div>
  );
}
