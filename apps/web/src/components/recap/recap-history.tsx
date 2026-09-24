import { cn } from "@/lib/utils";
import type { RecapListItem } from "@/lib/api/loose-types";

interface RecapHistoryProps {
  items: RecapListItem[];
  selectedDate: string;
  onSelect: (date: string) => void;
}

/** Port sidebar `#recap-history-list` di `recapLoadHistory()` lama. */
export function RecapHistory({ items, selectedDate, onSelect }: RecapHistoryProps) {
  if (!items.length) {
    return <p className="p-1.5 text-xs text-muted-foreground">No recaps yet.</p>;
  }

  return (
    <div className="flex flex-col gap-1">
      {items.map((it) => {
        const c = it.counts || {};
        const active = it.date === selectedDate;
        return (
          <button
            key={it.date}
            onClick={() => onSelect(it.date)}
            className={cn(
              "rounded-md border px-2 py-1.5 text-left font-mono text-[11px] transition-colors",
              active
                ? "border-primary/50 bg-primary/10"
                : "border-border hover:bg-accent",
            )}
          >
            <div className={active ? "text-primary" : "text-foreground"}>{it.date}</div>
            <div className="mt-0.5 text-[10px] text-muted-foreground">
              {c.articles ?? 0}a · {c.tweets ?? 0}t · {c.cves ?? 0}c
            </div>
          </button>
        );
      })}
    </div>
  );
}
