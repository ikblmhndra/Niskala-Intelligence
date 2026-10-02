import { GlobeIcon, MapPinIcon, StarIcon, TargetIcon } from "lucide-react";

import type { SectionKey } from "@/components/newsletter/types";

const ICONS = {
  highlight: StarIcon,
  apac: MapPinIcon,
  global_news: GlobeIcon,
  indonesia: TargetIcon,
} as const;

export function SectionIcon({ section, className }: { section: SectionKey; className?: string }) {
  const Icon = ICONS[section];
  return <Icon aria-hidden className={className} />;
}
