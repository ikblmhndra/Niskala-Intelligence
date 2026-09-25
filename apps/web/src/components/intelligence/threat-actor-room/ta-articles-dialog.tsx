"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { SimplePager } from "@/components/pager";

const PAGE_SIZE = 20;

/** Port `tawOpenArticlesModal()`/`_tawArtModalLoad()` (`ta.js:456-516`)
 * -- artikel yang nyebut threat actor ini, `GET /api/articles?
 * threat_actor=...`. */
export function TaArticlesDialog({ actorName, onClose }: { actorName: string | null; onClose: () => void }) {
  const [page, setPage] = useState(1);

  const query = useQuery({
    queryKey: ["ta-room", "ta-articles", actorName, page],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/articles", {
        params: { query: { threat_actor: [actorName!], page, page_size: PAGE_SIZE } },
      });
      if (error) throw error;
      return data;
    },
    enabled: actorName !== null,
  });

  const total = query.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <Dialog
      open={actorName !== null}
      onOpenChange={(open) => {
        if (!open) {
          onClose();
          setPage(1);
        }
      }}
    >
      <DialogContent className="max-h-[85vh] w-full max-w-2xl overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="font-mono text-sm">{actorName}</DialogTitle>
          <p className="font-mono text-xs text-muted-foreground">{total.toLocaleString()} article(s)</p>
        </DialogHeader>

        {query.isPending && <p className="py-6 text-center text-xs text-muted-foreground">Loading…</p>}
        {query.isError && <p className="py-6 text-center text-xs text-destructive">Failed to load articles.</p>}
        {query.data && query.data.articles.length === 0 && (
          <p className="py-6 text-center text-xs text-muted-foreground">No articles found for this threat actor.</p>
        )}

        <div className="space-y-2">
          {query.data?.articles.map((a) => (
            <div key={a.id} className="rounded-md border border-border bg-surface2 p-2.5">
              <a href={a.url} target="_blank" rel="noopener noreferrer" className="text-sm font-semibold text-foreground hover:underline">
                {a.title}
              </a>
              <div className="mt-1 font-mono text-[10px] text-muted-foreground">
                {[a.source, a.posted_on, a.news_type].filter(Boolean).join(" · ")}
              </div>
            </div>
          ))}
        </div>

        <div className="mt-2 flex justify-center">
          <SimplePager page={page} totalPages={totalPages} onPageChange={setPage} />
        </div>
      </DialogContent>
    </Dialog>
  );
}
