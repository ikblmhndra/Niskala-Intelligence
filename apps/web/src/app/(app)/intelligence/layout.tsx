import { IntelligenceNav } from "@/components/intelligence/intelligence-nav";

export default function IntelligenceLayout({ children }: { children: React.ReactNode }) {
  return (
    <div>
      <IntelligenceNav />
      {children}
    </div>
  );
}
