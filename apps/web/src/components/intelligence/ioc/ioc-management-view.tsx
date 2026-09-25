"use client";

import { useState } from "react";

import { IocTable } from "@/components/intelligence/ioc/ioc-table";
import { IocDetailDialog, type IocTarget } from "@/components/intelligence/ioc/ioc-detail-dialog";
import { IocAllowlistPanel } from "@/components/intelligence/ioc/ioc-allowlist-panel";
import { IocFpAnalyticsPanel } from "@/components/intelligence/ioc/ioc-fp-analytics-panel";

/** Port sub-view `iocmgmt` (`intel.js:28`) -- legacy muat 3 section
 * sekaligus pas view dibuka (`iocmgmtLoad()`+`allowlistLoad()`+
 * `fpAnalyticsLoad()`), bukan sub-tab terpisah. Disusun vertikal sama
 * di sini: tabel IOC utama di atas, Allowlist + FP Analytics di bawah. */
export function IocManagementView() {
  const [detailTarget, setDetailTarget] = useState<IocTarget | null>(null);

  return (
    <div className="flex flex-col gap-8">
      <IocTable onSelect={setDetailTarget} />

      <div className="border-t border-border pt-6">
        <IocAllowlistPanel />
      </div>

      <div className="border-t border-border pt-6">
        <IocFpAnalyticsPanel />
      </div>

      <IocDetailDialog target={detailTarget} onClose={() => setDetailTarget(null)} onDeleted={() => setDetailTarget(null)} />
    </div>
  );
}
