"use client";

import { SectionIcon } from "@/components/newsletter/section-icon";
import type { components } from "@/lib/api/schema";
import { Textarea } from "@/components/ui/textarea";
import { SECTION_MAX, type ComposerState, type SectionKey } from "@/components/newsletter/types";
import { cn } from "@/lib/utils";

type Article = components["schemas"]["ArticleOut"];

const SECTION_DISPLAY: { key: SectionKey; label: string; colorClass: string }[] = [
  { key: "highlight", label: "Highlight of the Week", colorClass: "text-warning" },
  { key: "apac", label: "APAC Threats", colorClass: "text-primary" },
  { key: "global_news", label: "Global Threats", colorClass: "text-tag-violet" },
  { key: "indonesia", label: "Indonesia (optional)", colorClass: "text-destructive" },
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
                "mb-3 flex items-center justify-between border-b border-border pb-2 text-sm font-semibold",
                def.colorClass,
              )}
            >
              <span className="flex items-center gap-2">
                <SectionIcon section={def.key} /> {def.label}
              </span>
              <span className="text-muted-foreground">
                {items.length} / {max}
              </span>
            </div>
            <div className="space-y-1.5">
              {items.length === 0 && (
                <div className="flex min-h-12 items-center justify-center rounded-xl border border-dashed border-border bg-background px-3 py-3">
                  <span className="text-sm text-muted-foreground">No articles yet — assign from the queue (max {max})</span>
                </div>
              )}
              {items.map((art) => {
                return (
                  <div key={art.id} className="rounded-xl border border-border bg-background p-2.5">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <div className="text-xs font-semibold text-foreground">{art.title}</div>
                        <div className="mt-0.5 font-mono text-xs text-muted-foreground">
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
                      className="mt-2 h-14 resize-y bg-black/20 font-mono text-xs"
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
