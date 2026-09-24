"use client";

import { useRef, useState } from "react";
import { toast } from "sonner";

import { getActiveClientId } from "@/lib/auth/client-id";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import type { components } from "@/lib/api/schema";

interface LockfileImportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onImported: () => void;
}

/** Port `pvImportLockfile()` (`pkgvuln.js:450`). Lewat proxy langsung
 * (bukan `api` client openapi-fetch) karena butuh `FormData` multipart
 * mentah -- pola sama kayak export CVE Excel, baca lewat `fetch()`
 * biasa. Format gak dikenal (bukan requirements.txt/package-lock.json/
 * package.json/go.mod/go.sum/pom.xml/poetry.lock) diam-diam jatuh ke
 * parser `requirements.txt` di backend (bukan ditolak) -- `accept`
 * di bawah cuma bantuan visual, bukan validasi keras. */
export function LockfileImportDialog({ open, onOpenChange, onImported }: LockfileImportDialogProps) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState<components["schemas"]["LockfileImportResult"] | null>(null);

  async function doImport() {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setImporting(true);
    setResult(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const clientId = getActiveClientId();
      const resp = await fetch("/api/proxy/api/pkgvuln/import-lockfile", {
        method: "POST",
        headers: clientId ? { "X-Client-ID": clientId } : undefined,
        body: fd,
      });
      if (!resp.ok) throw new Error(await resp.text());
      const data = (await resp.json()) as components["schemas"]["LockfileImportResult"];
      setResult(data);
      if (data.added > 0) onImported();
    } catch (e) {
      toast.error(`Import failed: ${(e as Error).message}`);
    } finally {
      setImporting(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        onOpenChange(o);
        if (!o) setResult(null);
      }}
    >
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Import Lockfile</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <input
            ref={fileRef}
            type="file"
            accept=".txt,.json,.mod,.sum,.xml,.lock"
            className="w-full text-xs"
          />
          <Button size="sm" disabled={importing} onClick={() => void doImport()}>
            {importing ? "Importing…" : "Upload"}
          </Button>
          {result && (
            <div className="rounded-md border border-border p-3 text-xs">
              <p>
                Parsed <strong>{result.parsed}</strong> · Added <strong className="text-primary">{result.added}</strong> · Skipped{" "}
                {result.skipped}
              </p>
              {result.packages.length > 0 && (
                <div className="mt-2 max-h-40 space-y-0.5 overflow-y-auto font-mono text-[10px] text-muted-foreground">
                  {result.packages.slice(0, 20).map((raw, i) => {
                    const p = raw as { name?: string; ecosystem?: string; version?: string };
                    return (
                      <div key={i}>
                        {p.name}@{p.version || "any"} ({p.ecosystem})
                      </div>
                    );
                  })}
                </div>
              )}
              {result.errors.length > 0 && (
                <div className="mt-2 space-y-0.5 text-[10px] text-destructive">
                  {result.errors.slice(0, 5).map((e, i) => (
                    <div key={i}>{e}</div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
