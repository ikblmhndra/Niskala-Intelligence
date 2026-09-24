"use client";

import { useState } from "react";

import { cn } from "@/lib/utils";
import { TweetList } from "@/components/xintel/tweet-list";
import { MonitoredAccounts } from "@/components/xintel/monitored-accounts";

const SUB_TABS = [
  { id: "tweets", label: "Tweets" },
  { id: "accounts", label: "Monitored Accounts" },
] as const;

type SubTab = (typeof SUB_TABS)[number]["id"];

/**
 * Port `tab_xintel.html` + `xintel.js`. 𝕏 API balance chip (`GET
 * /api/tweets/balance`) SENGAJA gak diport -- backend-nya juga gak ada,
 * `routers/tweets.py` bilang eksplisit "passthrough eksternal doang, gak
 * genting buat inti" (keputusan Fase 7.3, bukan keputusan baru di sini).
 */
export default function XIntelPage() {
  const [tab, setTab] = useState<SubTab>("tweets");

  return (
    <div>
      <div className="mb-4 flex gap-1.5 border-b border-border pb-3">
        {SUB_TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={cn(
              "rounded-md border px-3.5 py-1.5 font-mono text-xs tracking-wide transition-colors",
              tab === t.id
                ? "border-primary/40 bg-primary/10 text-primary"
                : "border-border text-muted-foreground hover:bg-accent",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "tweets" ? <TweetList /> : <MonitoredAccounts />}
    </div>
  );
}
