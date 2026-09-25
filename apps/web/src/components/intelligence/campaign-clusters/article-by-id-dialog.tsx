"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import { ArticleModal } from "@/components/newsroom/article-modal";

/** Port `openArticleById()` (`clusters.js:754-764`) -- `ArticleModal`
 * (Grup D) sudah nerima objek `Article` penuh, di sini di-fetch dulu
 * by id (member artikel cluster cuma nyimpen id, bukan objek utuh). */
export function ArticleByIdDialog({ articleId, onClose }: { articleId: number | null; onClose: () => void }) {
  const query = useQuery({
    queryKey: ["campaign-clusters", "article-by-id", articleId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/articles/{article_id}", { params: { path: { article_id: articleId! } } });
      if (error) throw error;
      return data;
    },
    enabled: articleId !== null,
  });

  return <ArticleModal article={query.data ?? null} onOpenChange={(open) => !open && onClose()} />;
}
