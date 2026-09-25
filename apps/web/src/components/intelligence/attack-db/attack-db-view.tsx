"use client";

import { useState } from "react";

import { cn } from "@/lib/utils";
import { SyncStatusCards } from "@/components/intelligence/attack-db/sync-status-cards";
import { TechniquesPanel } from "@/components/intelligence/attack-db/techniques-panel";
import { GroupsPanel } from "@/components/intelligence/attack-db/groups-panel";
import { SoftwarePanel } from "@/components/intelligence/attack-db/software-panel";
import { MitigationsPanel } from "@/components/intelligence/attack-db/mitigations-panel";
import { AttackDetailDialog, type DetailTarget } from "@/components/intelligence/attack-db/attack-detail-dialog";

const BROWSE_TABS = [
  { value: "techniques", label: "Techniques" },
  { value: "groups", label: "Groups" },
  { value: "software", label: "Software" },
  { value: "mitigations", label: "Mitigations" },
] as const;
type BrowseTab = (typeof BROWSE_TABS)[number]["value"];

/** Port `loadAttackDB()`/`_attackdbSetActiveTab()` (`attack_db.js:1-24,126-161`)
 * -- render CUMA panel aktif (bukan mount ke-4 sub-tab sekaligus, biar
 * gak nembak 4 query bareng), satu `AttackDetailDialog` dibagi ke 3
 * panel clickable (Mitigations gak punya detail, lihat komponennya). */
export function AttackDbView() {
  const [tab, setTab] = useState<BrowseTab>("techniques");
  const [detailTarget, setDetailTarget] = useState<DetailTarget>(null);

  return (
    <div>
      <SyncStatusCards />

      <div className="mb-4 flex gap-1.5">
        {BROWSE_TABS.map((t) => (
          <button
            key={t.value}
            type="button"
            onClick={() => setTab(t.value)}
            className={cn(
              "rounded-md border px-3 py-1.5 font-mono text-xs tracking-wide transition-colors",
              tab === t.value
                ? "border-primary/40 bg-primary/10 text-primary"
                : "border-border text-muted-foreground hover:bg-accent",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "techniques" && <TechniquesPanel onSelect={setDetailTarget} />}
      {tab === "groups" && <GroupsPanel onSelect={setDetailTarget} />}
      {tab === "software" && <SoftwarePanel onSelect={setDetailTarget} />}
      {tab === "mitigations" && <MitigationsPanel />}

      <AttackDetailDialog target={detailTarget} onNavigate={setDetailTarget} onClose={() => setDetailTarget(null)} />
    </div>
  );
}
