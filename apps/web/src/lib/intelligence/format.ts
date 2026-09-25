/** Admiralty reliability grade -> warna badge. A/B baik (hijau/biru),
 * C/D sedang (kuning/oranye), E/F buruk (merah/abu), niru urutan
 * `_RELIABILITY_ORDER` (`source_score.py`) tapi di-mapping ke token
 * Tailwind, bukan warna literal legacy. */
export const GRADE_BADGE_CLASS: Record<string, string> = {
  A: "text-success border-success/40",
  B: "text-primary border-primary/40",
  C: "text-warning border-warning/40",
  D: "text-warning border-warning/40",
  E: "text-destructive border-destructive/40",
  F: "text-muted-foreground border-border",
};
