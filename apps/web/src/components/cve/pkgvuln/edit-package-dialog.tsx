"use client";

import { useState } from "react";
import { toast } from "sonner";

import { api } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { components } from "@/lib/api/schema";
import type { PkgPatchResult } from "@/lib/api/loose-types";

const ECOSYSTEMS = ["npm", "PyPI", "Go", "Maven", "crates.io", "NuGet", "RubyGems", "Packagist", "Hex"];

interface EditPackageDialogProps {
  pkg: components["schemas"]["MonitoredPackageOut"] | null;
  onClose: () => void;
  onSaved: () => void;
}

/** Port `pvShowEditModal()`/`pvSaveEdit()` (`pkgvuln.js:840-874`).
 * Parent (`PackagesPanel`) keys this component by `pkg?.id` so local
 * state re-seeds fresh per package without an effect. */
export function EditPackageDialog({ pkg, onClose, onSaved }: EditPackageDialogProps) {
  const [version, setVersion] = useState(pkg?.version ?? "");
  const [ecosystem, setEcosystem] = useState(pkg?.ecosystem ?? "npm");
  const [saving, setSaving] = useState(false);

  async function save() {
    if (!pkg) return;
    setSaving(true);
    try {
      const { data, error } = await api.PATCH("/api/pkgvuln/packages/{pkg_id}", {
        params: { path: { pkg_id: pkg.id } },
        body: { version: version.trim() || null, ecosystem },
      });
      if (error) throw new Error(JSON.stringify(error));
      const d = data as unknown as PkgPatchResult;
      toast.success(d.changed ? "Package updated, rescan queued." : "No changes.");
      onSaved();
      onClose();
    } catch (e) {
      toast.error(`Save failed: ${(e as Error).message}`);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog
      open={pkg !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      {pkg && (
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle className="font-mono">{pkg.name}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="flex flex-col gap-1">
              <Label className="text-sm font-medium text-muted-foreground">Version</Label>
              <Input value={version} onChange={(e) => setVersion(e.target.value)} placeholder="leave empty for any" className="text-xs" />
            </div>
            <div className="flex flex-col gap-1">
              <Label className="text-sm font-medium text-muted-foreground">Ecosystem</Label>
              <Select value={ecosystem} onValueChange={(v) => v && setEcosystem(v)}>
                <SelectTrigger size="sm" className="w-full text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ECOSYSTEMS.map((e) => (
                    <SelectItem key={e} value={e} className="text-xs">
                      {e}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button disabled={saving} onClick={() => void save()}>
              {saving ? "Saving…" : "Save"}
            </Button>
          </DialogFooter>
        </DialogContent>
      )}
    </Dialog>
  );
}
