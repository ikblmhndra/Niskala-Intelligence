"use client";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import type { PreviewDialogState } from "@/components/newsletter/types";

interface Props {
  state: PreviewDialogState;
  onOpenChange: (open: boolean) => void;
  onSendDraft: () => void;
  sending: boolean;
  onResendSaved: (id: number, week: number, year: number) => void;
  resending: boolean;
}

/** Port `#modal-overlay`/`#preview-iframe` (`newsletter.html:401-416`) --
 * dipakai DUA mode: "compose" (hasil `POST /preview` dari composition
 * yang lagi disusun, footer "Send Draft Email") dan "saved" (hasil
 * `GET /{id}/html` dari histori, footer "Resend") -- port
 * `openPreview()`/`previewSaved()` yang keduanya numpang modal yang
 * SAMA di legacy. */
export function NewsletterPreviewDialog({ state, onOpenChange, onSendDraft, sending, onResendSaved, resending }: Props) {
  return (
    <Dialog open={state.open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[85vh] max-w-3xl flex-col gap-0 overflow-hidden p-0">
        <DialogHeader className="border-b border-border px-4 py-3">
          <DialogTitle className="font-mono text-xs tracking-[0.1em] text-primary">{state.title}</DialogTitle>
        </DialogHeader>
        <div className="h-[65vh] overflow-hidden bg-white">
          {state.html === null ? (
            <div className="flex h-full items-center justify-center text-xs text-muted-foreground">Loading…</div>
          ) : (
            <iframe title="Newsletter preview" sandbox="allow-same-origin" srcDoc={state.html} className="h-full w-full border-0" />
          )}
        </div>
        <div className="flex justify-end gap-2 border-t border-border px-4 py-3">
          <Button variant="outline" size="sm" onClick={() => onOpenChange(false)}>
            Close
          </Button>
          {state.mode === "compose" ? (
            <Button size="sm" onClick={onSendDraft} disabled={sending}>
              {sending ? "Sending…" : "Send Draft Email"}
            </Button>
          ) : (
            <Button
              size="sm"
              disabled={resending || state.savedId == null}
              onClick={() => state.savedId != null && onResendSaved(state.savedId, state.week ?? 0, state.year ?? 0)}
            >
              {resending ? "Resending…" : "Resend"}
            </Button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
