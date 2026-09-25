import type { components } from "@/lib/api/schema";

type Article = components["schemas"]["ArticleOut"];

/** Article shape carried in the `newsletter_queue` localStorage key --
 * legacy (`newsletter.html:1050-1057`) read both `_id` (Mongo) and `id`
 * (fallback), new backend only ever writes `id` (Postgres int) but `_id`
 * is kept as an alias for exact contract compatibility with
 * `article-modal.tsx`'s "+ Newsletter" button. */
export type QueueArticle = Article & { _id: number };

const QUEUE_KEY = "newsletter_queue";

export function getQueue(): QueueArticle[] {
  try {
    const raw = localStorage.getItem(QUEUE_KEY);
    if (!raw) return [];
    const parsed: Array<Article & { _id?: number; id?: number }> = JSON.parse(raw);
    return parsed
      .map((a) => ({ ...a, _id: a._id ?? a.id }) as QueueArticle)
      .filter((a) => typeof a._id === "number");
  } catch {
    return [];
  }
}

function writeQueue(queue: QueueArticle[]) {
  try {
    localStorage.setItem(QUEUE_KEY, JSON.stringify(queue));
  } catch {
    // localStorage unavailable (private mode dst) -- port apa adanya, legacy juga silent-fail
  }
}

export function isQueued(articleId: number): boolean {
  return getQueue().some((a) => a._id === articleId);
}

/** Port `addToQueue()` (`newsletter.html:1217-1225`). */
export function addToQueue(article: Article): "queued" | "already" {
  const queue = getQueue();
  if (queue.some((a) => a._id === article.id)) return "already";
  queue.push({ ...article, _id: article.id } as QueueArticle);
  writeQueue(queue);
  return "queued";
}

/** Port `removeFromQueue()` (`newsletter.html:1227-1231`). */
export function removeFromQueue(articleId: number) {
  writeQueue(getQueue().filter((a) => a._id !== articleId));
}

/** Port `clearQueue()` (`newsletter.html:1233-1237`). */
export function clearQueue() {
  writeQueue([]);
}
