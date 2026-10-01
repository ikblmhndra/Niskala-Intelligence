"use client";

import { useState } from "react";

import { HealthSummaryBar } from "@/components/scrapers/health-summary-bar";
import { SchedulerStatus } from "@/components/scrapers/scheduler-status";
import { ScrapersTable } from "@/components/scrapers/scrapers-table";
import { ScraperDetailDialog } from "@/components/scrapers/scraper-detail-dialog";

/** Halaman control plane scraper (Fase 9, H4) -- halaman SENDIRI
 * (`/scrapers`), bukan digabung widget di `/dashboard` (keputusan user
 * 2026-09-25: dashboard umum tetap general-purpose, scraper dapet
 * ruang sendiri karena scope-nya emang beda -- ops tool, bukan metrik
 * baca-doang). `selected` nyimpen status SEKALIAN (bukan cuma id) --
 * `ScrapersTable` udah ngitung status per-baris yang bener (cross-ref
 * `/health`'s `problems` + `enabled`), lebih akurat daripada nebak ulang
 * di sini (scraper yang `disabled` gak nongol di `problems`, jadi nebak
 * "ok" dari situ doang bakal salah). */
export function ScrapersView() {
  const [selected, setSelected] = useState<{ id: string; status: string } | null>(null);

  return (
    <div className="pb-10">
      <SchedulerStatus />
      <HealthSummaryBar onSelectProblem={(id, status) => setSelected({ id, status })} />
      <ScrapersTable onOpenDetail={(id, status) => setSelected({ id, status })} />
      <ScraperDetailDialog
        scraperId={selected?.id ?? null}
        healthStatus={selected?.status || undefined}
        onOpenChange={(open) => !open && setSelected(null)}
      />
    </div>
  );
}
