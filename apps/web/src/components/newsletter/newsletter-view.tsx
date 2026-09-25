"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";

import { api } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import type { components } from "@/lib/api/schema";
import type {
  NewsletterDraftResult,
  NewsletterPreviewResult,
  NewsletterResendResult,
  NewsletterSourceHint,
} from "@/lib/api/loose-types";
import { addToQueue, clearQueue, getQueue, removeFromQueue, type QueueArticle } from "@/lib/newsletter/queue";
import { getActiveClientId } from "@/lib/auth/client-id";
import {
  DEFAULT_TEMPLATE_STATE,
  EMPTY_COMPOSER_STATE,
  PREVIEW_DIALOG_CLOSED,
  SECTION_DEFS,
  SECTION_MAX,
  type ComposerState,
  type PreviewDialogState,
  type SectionKey,
  type TemplateState,
} from "@/components/newsletter/types";
import { NewsletterQueuePanel } from "@/components/newsletter/newsletter-queue-panel";
import { NewsletterComposerSections } from "@/components/newsletter/newsletter-composer-sections";
import { NewsletterTemplatePanel } from "@/components/newsletter/newsletter-template-panel";
import { NewsletterPreviewDialog } from "@/components/newsletter/newsletter-preview-dialog";
import { NewsletterHistoryPanel } from "@/components/newsletter/newsletter-history-panel";

type Article = components["schemas"]["ArticleOut"];
type NewsletterSectionsBody = components["schemas"]["NewsletterSectionsBody"];

const SECTION_LABEL: Record<SectionKey, string> = Object.fromEntries(SECTION_DEFS.map((s) => [s.key, s.label])) as Record<
  SectionKey,
  string
>;

/** Port `newsletter.html` (1261 baris, route standalone di app lama --
 * di sini route Next.js biasa `/newsletter`, nav udah disiapin Grup A
 * `app-header.tsx`). Grup H, sub-grup terakhir Fase 8 -- numpang
 * komponen Mindmap (G5) buat "Mind Map" per histori. */
export function NewsletterView() {
  const [state, setState] = useState<ComposerState>(EMPTY_COMPOSER_STATE);
  const [template, setTemplate] = useState<TemplateState>(DEFAULT_TEMPLATE_STATE);
  const [queue, setQueue] = useState<QueueArticle[]>(() => getQueue());
  const [preview, setPreview] = useState<PreviewDialogState>(PREVIEW_DIALOG_CLOSED);
  const [sending, setSending] = useState(false);
  const [resendingId, setResendingId] = useState<number | null>(null);
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0);

  const hintsQuery = useQuery({
    queryKey: ["newsletter", "source-hints"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/newsletter/source-hints");
      if (error) throw error;
      return data as unknown as Record<string, NewsletterSourceHint>;
    },
  });

  function pushToQueue(article: Article) {
    addToQueue(article);
    setQueue((prev) => (prev.some((a) => a._id === article.id) ? prev : [...prev, { ...article, _id: article.id } as QueueArticle]));
  }

  function popFromQueue(articleId: number) {
    removeFromQueue(articleId);
    setQueue((prev) => prev.filter((a) => a._id !== articleId));
  }

  function handleClearQueue() {
    clearQueue();
    setQueue([]);
    toast.info("Queue cleared");
  }

  function assign(section: SectionKey, article: Article) {
    if (section === "highlight") {
      if (state.highlight && state.highlight.id !== article.id) pushToQueue(state.highlight);
      setState((prev) => ({ ...prev, highlight: article }));
    } else {
      if (state[section].some((a) => a.id === article.id)) {
        toast.info("Already in section");
        return;
      }
      const arr = state[section];
      let displaced: Article | undefined;
      let nextArr = arr;
      if (arr.length >= SECTION_MAX[section]) {
        displaced = arr[0];
        nextArr = arr.slice(1);
      }
      nextArr = [...nextArr, article];
      if (displaced) pushToQueue(displaced);
      setState((prev) => ({ ...prev, [section]: nextArr }));
    }
    popFromQueue(article.id);
    toast.success(`Added to ${SECTION_LABEL[section]}`);
  }

  function removeFromSection(section: SectionKey, articleId: number) {
    if (section === "highlight") {
      if (state.highlight) pushToQueue(state.highlight);
      setState((prev) => ({ ...prev, highlight: null }));
    } else {
      const article = state[section].find((a) => a.id === articleId);
      setState((prev) => ({ ...prev, [section]: prev[section].filter((a) => a.id !== articleId) }));
      if (article) pushToQueue(article);
    }
  }

  function updateNote(articleId: number, value: string) {
    setState((prev) => {
      const notes = { ...prev.notes };
      const key = String(articleId);
      if (value.trim()) notes[key] = value;
      else delete notes[key];
      return { ...prev, notes };
    });
  }

  function buildPayload(): NewsletterSectionsBody | null {
    if (!state.highlight) {
      toast.error("Add a Highlight article first");
      return null;
    }
    if (!state.apac.length && !state.global_news.length) {
      toast.error("Add at least one APAC or Global article");
      return null;
    }
    return {
      highlight: state.highlight.id,
      apac: state.apac.map((a) => a.id),
      global_news: state.global_news.map((a) => a.id),
      indonesia: state.indonesia.map((a) => a.id),
      custom_css: template.customCss.trim(),
      custom_intro: template.customIntro.trim(),
      custom_footer: template.customFooter.trim(),
      notes: state.notes,
      include_clusters: template.includeClusters,
      cluster_days: template.clusterDays,
    };
  }

  async function handlePreview() {
    const payload = buildPayload();
    if (!payload) return;
    setPreview({ open: true, title: "NEWSLETTER PREVIEW", html: null, mode: "compose" });
    try {
      const { data, error } = await api.POST("/api/newsletter/preview", { body: payload });
      if (error) throw error;
      const result = data as unknown as NewsletterPreviewResult;
      setPreview({
        open: true,
        title: `NEWSLETTER PREVIEW — Week ${result.week}, ${result.year}`,
        html: result.html,
        mode: "compose",
      });
    } catch (e) {
      setPreview({
        open: true,
        title: "NEWSLETTER PREVIEW",
        html: `<body style="font-family:sans-serif;padding:20px;color:#d32f2f">Error: ${(e as Error).message}</body>`,
        mode: "compose",
      });
      toast.error(`Preview failed: ${(e as Error).message}`);
    }
  }

  async function handleSendDraft() {
    const payload = buildPayload();
    if (!payload) return;
    setSending(true);
    try {
      const { data, error } = await api.POST("/api/newsletter/draft-email", { body: payload });
      if (error) throw error;
      const result = data as unknown as NewsletterDraftResult;
      toast.success(`Draft created — ${result.method} · Week ${result.week}, ${result.year}`);
      setPreview(PREVIEW_DIALOG_CLOSED);
      setHistoryRefreshKey((k) => k + 1);
    } catch (e) {
      toast.error(`Send failed: ${(e as Error).message}`);
    } finally {
      setSending(false);
    }
  }

  async function handlePreviewSaved(id: number, week: number, year: number) {
    setPreview({ open: true, title: `SAVED NEWSLETTER — Week ${week}, ${year}`, html: null, mode: "saved", savedId: id, week, year });
    try {
      const clientId = getActiveClientId();
      const resp = await fetch(`/api/proxy/api/newsletter/${id}/html`, clientId ? { headers: { "X-Client-ID": clientId } } : undefined);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const html = await resp.text();
      setPreview((p) => (p.savedId === id ? { ...p, html } : p));
    } catch (e) {
      setPreview((p) =>
        p.savedId === id
          ? { ...p, html: `<body style="font-family:sans-serif;padding:20px;color:#d32f2f">Error: ${(e as Error).message}</body>` }
          : p,
      );
      toast.error("Failed to load saved newsletter");
    }
  }

  async function handleResend(id: number, week: number, year: number) {
    setResendingId(id);
    try {
      const { data, error } = await api.POST("/api/newsletter/{newsletter_id}/resend", { params: { path: { newsletter_id: id } } });
      if (error) throw error;
      const result = data as unknown as NewsletterResendResult;
      toast.success(`Draft resent — ${result.method} · Week ${week}, ${year}`);
      setPreview((p) => (p.savedId === id ? PREVIEW_DIALOG_CLOSED : p));
    } catch (e) {
      toast.error(`Resend failed: ${(e as Error).message}`);
    } finally {
      setResendingId(null);
    }
  }

  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_420px]">
      <div className="rounded-lg border border-border bg-surface p-4">
        <NewsletterQueuePanel
          queue={queue}
          paywallHints={hintsQuery.data ?? {}}
          onAssign={assign}
          onRemove={popFromQueue}
          onClearAll={handleClearQueue}
        />
      </div>

      <div className="rounded-lg border border-border bg-surface p-4">
        <div className="mb-3 flex items-center justify-between border-b border-border pb-3">
          <div className="font-mono text-[11px] tracking-[0.1em] text-muted-foreground uppercase">Newsletter Composer</div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={handlePreview}>
              Preview
            </Button>
            <Button size="sm" onClick={handleSendDraft} disabled={sending}>
              {sending ? "Sending…" : "Send Draft Email"}
            </Button>
          </div>
        </div>

        <NewsletterComposerSections state={state} onRemove={removeFromSection} onNoteChange={updateNote} />
        <NewsletterTemplatePanel value={template} onChange={setTemplate} />
        <NewsletterHistoryPanel refreshKey={historyRefreshKey} onPreview={handlePreviewSaved} onResend={handleResend} resendingId={resendingId} />
      </div>

      <NewsletterPreviewDialog
        state={preview}
        onOpenChange={(open) => setPreview((p) => ({ ...p, open }))}
        onSendDraft={handleSendDraft}
        sending={sending}
        onResendSaved={handleResend}
        resending={resendingId != null}
      />
    </div>
  );
}
