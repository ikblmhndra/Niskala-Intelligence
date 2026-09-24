import { Button } from "@/components/ui/button";

interface SimplePagerProps {
  page: number;
  totalPages: number;
  totalLabel?: string;
  onPageChange: (page: number) => void;
}

/**
 * Prev/next pager client-state (bukan URL) -- shadcn `pagination.tsx`
 * yang ke-install Grup A itu `<a href>`-based (buat pagination lewat URL
 * asli), gak cocok buat list yang state halamannya di React state
 * (`loadXIntel(page)`/`loadAuditLog(page)` lama juga cuma Prev/Next + info
 * halaman, bukan link angka per halaman). Dipakai bareng di X Intel tweet
 * list dan Admin audit log.
 */
export function SimplePager({ page, totalPages, totalLabel, onPageChange }: SimplePagerProps) {
  if (totalPages <= 1) return null;
  return (
    <div className="flex items-center justify-center gap-3 font-mono text-xs text-muted-foreground">
      <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
        ◀ Prev
      </Button>
      <span>
        Page <strong className="text-foreground">{page}</strong> / {totalPages}
        {totalLabel ? ` · ${totalLabel}` : ""}
      </span>
      <Button
        size="sm"
        variant="outline"
        disabled={page >= totalPages}
        onClick={() => onPageChange(page + 1)}
      >
        Next ▶
      </Button>
    </div>
  );
}
