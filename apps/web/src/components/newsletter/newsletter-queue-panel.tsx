"use client";

import { TriangleAlertIcon, XIcon } from "lucide-react";
import type { components } from "@/lib/api/schema";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { QueueArticle } from "@/lib/newsletter/queue";
import type { NewsletterSourceHint } from "@/lib/api/loose-types";
import { SECTION_DEFS, type SectionKey } from "@/components/newsletter/types";

type Article = components["schemas"]["ArticleOut"];

interface Props {
  queue: QueueArticle[];
  paywallHints: Record<string, NewsletterSourceHint>;
  onAssign: (section: SectionKey, article: Article) => void;
  onRemove: (articleId: number) => void;
  onClearAll: () => void;
}

/** Port left panel "Queued Articles" (`newsletter.html:287-305`,
 * `renderQueuedArticles()` `newsletter.html:1054-1109`) -- SATU-SATUNYA
 * jalur artikel masuk ke composer di legacy (search/filter panel
 * `loadArticles()`/`renderArticles()` di file yang sama gak pernah
 * dipanggil `init()` DAN elemen HTML-nya `f-search`/`f-date-start`/dst
 * gak ada di markup -- dead code, sengaja gak diport, sama pola kayak
 * `requireTAAuth()` G6). Queue diisi tombol "+ Newsletter" di
 * `ArticleModal` (Grup D, `article-modal.tsx`) lewat localStorage key
 * `newsletter_queue` -- kontrak SAMA PERSIS kayak lama, lihat
 * `lib/newsletter/queue.ts`. */
export function NewsletterQueuePanel({ queue, paywallHints, onAssign, onRemove, onClearAll }: Props) {
  return (
    <div className="flex h-full flex-col">
      <div className="mb-3 flex items-center justify-between border-b border-border pb-3">
        <div className="font-mono text-[13px] tracking-[0.1em] text-muted-foreground uppercase">Queued Articles</div>
        {queue.length > 0 && (
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs text-primary">
              {queue.length} article{queue.length === 1 ? "" : "s"}
            </span>
            <Button variant="ghost" size="sm" className="h-6 px-2 text-xs" onClick={onClearAll}>
              Clear All
            </Button>
          </div>
        )}
      </div>

      <div className="flex-1 space-y-1.5 overflow-y-auto">
        {queue.length === 0 && (
          <p className="py-10 text-center text-xs text-muted-foreground">
            No queued articles — go to Newsroom and click &quot;+ Newsletter&quot; on an article.
          </p>
        )}
        {queue.map((a) => {
          const isPaywall = paywallHints[a.source]?.paywall_likely;
          const countries = [...(a.victim_countries ?? []), ...(a.mentioned_countries ?? [])].slice(0, 3);
          const actors = (a.threat_actors ?? []).slice(0, 2);
          return (
            <div key={a._id} className="rounded-2xl border border-border bg-surface shadow-sm p-2.5">
              <div className="flex items-start gap-2">
                <div className="min-w-0 flex-1">
                  <div className="text-xs font-semibold text-foreground">{a.title}</div>
                  <div className="mt-0.5 font-mono text-xs text-muted-foreground">
                    {a.source} · {a.posted_on}
                  </div>
                  <div className="mt-1.5 flex flex-wrap gap-1">
                    {a.news_type && (
                      <Badge variant="outline" className="text-xs">
                        {a.news_type}
                      </Badge>
                    )}
                    {countries.map((c) => (
                      <Badge key={c} variant="outline" className="text-xs">
                        {c}
                      </Badge>
                    ))}
                    {actors.map((t) => (
                      <Badge key={t} variant="destructive" className="text-xs">
                        {t}
                      </Badge>
                    ))}
                    {isPaywall && (
                      <Badge
                        variant="outline"
                        className="border-warning/40 bg-warning/10 text-xs text-warning"
                        title="Paywall detected — summary will use metadata"
                      >
                        <TriangleAlertIcon aria-hidden /> Paywall
                      </Badge>
                    )}
                  </div>
                </div>
                <div className="flex shrink-0 flex-col items-end gap-1.5">
                  <DropdownMenu>
                    <DropdownMenuTrigger
                      render={<Button variant="outline" size="sm" className="h-6 w-6 p-0 text-sm leading-none" title="Add to section" />}
                    >
                      +
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      {SECTION_DEFS.map((s) => (
                        <DropdownMenuItem key={s.key} onClick={() => onAssign(s.key, a)}>
                          {s.icon} {s.label}
                        </DropdownMenuItem>
                      ))}
                    </DropdownMenuContent>
                  </DropdownMenu>
                  <button
                    type="button"
                    onClick={() => onRemove(a._id)}
                    title="Remove from queue"
                    className="font-mono text-xs text-muted-foreground transition-colors hover:text-destructive"
                  >
                    <XIcon aria-hidden />
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
