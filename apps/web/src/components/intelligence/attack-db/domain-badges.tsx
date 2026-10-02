import { Badge } from "@/components/ui/badge";

const DOMAIN_LABELS: Record<string, string> = {
  "enterprise-attack": "Enterprise",
  "ics-attack": "ICS",
  "mobile-attack": "Mobile",
};

const DOMAIN_CLASS: Record<string, string> = {
  "enterprise-attack": "text-primary border-primary/40",
  "ics-attack": "text-warning border-warning/40",
  "mobile-attack": "text-secondary border-secondary/40",
};

/** Port `_domainBadges()` (`attack_db.js:502-509`). */
export function DomainBadges({ domains }: { domains: string[] }) {
  return (
    <>
      {domains.map((d) => (
        <Badge key={d} variant="outline" className={`mr-1 text-xs ${DOMAIN_CLASS[d] ?? "text-muted-foreground"}`}>
          {DOMAIN_LABELS[d] ?? d}
        </Badge>
      ))}
    </>
  );
}
