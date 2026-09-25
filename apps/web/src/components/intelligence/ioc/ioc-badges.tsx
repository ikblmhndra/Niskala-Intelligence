import { actionabilityStyle, confidenceStyle, iocTypeStyle } from "@/lib/intelligence/ioc-style";

function Chip({ label, bg, border, color }: { label: string; bg: string; border: string; color: string }) {
  return (
    <span
      className="rounded-sm border px-1.5 py-0.5 font-mono text-[9px]"
      style={{ background: bg, borderColor: border, color }}
    >
      {label}
    </span>
  );
}

export function IocTypeBadge({ type }: { type: string }) {
  const s = iocTypeStyle(type);
  return <Chip label={s.label} bg={s.bg} border={s.border} color={s.color} />;
}

export function IocActionabilityChip({ label }: { label: string | null }) {
  if (!label) return null;
  const s = actionabilityStyle(label);
  return <Chip label={s.label} bg={s.bg} border={s.border} color={s.color} />;
}

export function IocConfidenceChip({ score }: { score: number | null }) {
  if (score == null) return null;
  const s = confidenceStyle(score);
  return <Chip label={String(score)} bg={s.bg} border={s.border} color={s.color} />;
}
