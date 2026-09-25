"use client";

import type { components } from "@/lib/api/schema";
import { Textarea } from "@/components/ui/textarea";
import { SECTION_MAX, type ComposerState, type SectionKey } from "@/components/newsletter/types";
import { cn } from "@/lib/utils";

type Article = components["schemas"]["ArticleOut"];

const SECTION_DISPLAY: { key: SectionKey; label: string; icon: string; colorClass: string }[] = [
  { key: "highlight", label: "Highlight of the Week", icon: "⭐", colorClass: "text-warning" },
  { key: "apac", label: "APAC Threats", icon: "🌏", colorClass: "text-primary" },
  { key: "global_news", label: "Global Threats", icon: "🌐", colorClass: "text-purple-400" },
  { key: "indonesia", label: "Indonesia (optional)", icon: "🇮🇩", colorClass: "text-destructive" },
];

interface Props {
  state: ComposerState;
  onRemove: (section: SectionKey, articleId: number) => void;
  onNoteChange: (articleId: number, value: string) => void;
}

/** Port 4 section block (`newsletter.html:317-351`, slot rendering
 * `renderSection()` `newsletter.html:704-737`). */
export function NewsletterComposerSections({ state, onRemove, onNoteChange }: Props) {
  return (
    <div className="space-y-5">
      {SECTION_DISPLAY.map((def) => {
        const items: Article[] = def.key === "highlight" ? (state.highlight ? [state.highlight] : []) : state[def.key];
        const max = SECTION_MAX[def.key];
        return (
          <div key={def.key}>
            <div
              className={cn(
                "mb-2 flex items-center justify-between border-b border-border pb-1.5 font-mono text-[10px] tracking-[0.1em] uppercase",
                def.colorClass,
              )}
            >
              <span>
                {def.icon} {def.label}
              </span>
              <span className="text-muted-foreground">
                {items.length} / {max}
              </span>
            </div>
            <div className="space-y-1.5">
              {Array.from({ length: max }).map((_, i) => {
                const art = items[i];
                if (!art) {
                  return (
                    <div
                      key={i}
                      className="flex min-h-9 items-center justify-center rounded-md border border-dashed border-border bg-surface px-3 py-2"
                    >
                      <span className="font-mono text-[10px] text-muted-foreground">— empty —</span>
                    </div>
                  );
                }
                return (
                  <div key={art.id} className="rounded-md border border-border bg-surface2 p-2.5">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <div className="text-xs font-semibold text-foreground">{art.title}</div>
                        <div className="mt-0.5 font-mono text-[9px] text-muted-foreground">
                          {art.source} · {art.posted_on}
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => onRemove(def.key, art.id)}
                        title="Remove"
                        className="shrink-0 font-mono text-xs text-muted-foreground transition-colors hover:text-destructive"
                      >
                        ✕
                      </button>
                    </div>
                    <Textarea
                      placeholder="Analyst notes (optional)…"
                      value={state.notes[String(art.id)] ?? ""}
                      onChange={(e) => onNoteChange(art.id, e.target.value)}
                      className="mt-2 h-14 resize-y bg-black/20 font-mono text-[10px]"
                    />
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
