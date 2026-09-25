"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

/** `POST /{id}/disable` (Fase 9 H3) -- `reason` opsional tapi diminta
 * eksplisit di sini (bukan disable diam-diam), landing di `ScraperConfig.
 * paused_reason` buat analis lain yang lihat kenapa scraper ini mati. */
export function DisableScraperDialog({
  scraperId,
  onOpenChange,
}: {
  scraperId: string | null;
  onOpenChange: (open: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const [reason, setReason] = useState("");

  const mutation = useMutation({
    mutationFn: async () => {
      const { error } = await api.POST("/api/scraper/{scraper_id}/disable", {
        params: { path: { scraper_id: scraperId! } },
        body: { reason: reason.trim() || null },
      });
      if (error) throw error;
    },
    onSuccess: () => {
      toast.success(`${scraperId} disabled`);
      void queryClient.invalidateQueries({ queryKey: ["scrapers"] });
      setReason("");
      onOpenChange(false);
    },
    onError: (e: Error) => toast.error(`Disable failed: ${e.message}`),
  });

  return (
    <Dialog open={scraperId !== null} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle className="font-heading">Disable scraper</DialogTitle>
        </DialogHeader>
        <p className="font-mono text-xs text-muted-foreground">
          Scraper: <span className="text-foreground">{scraperId}</span>
        </p>
        <div className="space-y-1.5">
          <Label className="font-mono text-[9px] text-muted-foreground uppercase">Reason (optional)</Label>
          <Textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="e.g. selector broken, waiting on site redesign…"
            className="h-20 font-mono text-xs"
          />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={() => mutation.mutate()} disabled={mutation.isPending}>
            Disable
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
