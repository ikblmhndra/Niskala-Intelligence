"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import type { TaStats } from "@/lib/api/loose-types";
import { ChartCard, DashboardSectionLabel, MapCard, StatBox } from "@/components/dashboard/stat-box";
import { AttentionBand } from "@/components/dashboard/attention-band";
import { BreakdownList } from "@/components/dashboard/breakdown-list";
import { CountryMap } from "@/components/dashboard/country-map";
import { HorizontalBarChart, TimelineChart } from "@/components/dashboard/charts";
import { Skeleton } from "@/components/ui/skeleton";

function toTitleCase(s: string): string {
  return s.replace(/\w\S*/g, (w) => w.charAt(0).toUpperCase() + w.slice(1));
}

function useDashboardStats() {
  return useQuery({
    queryKey: ["dashboard", "stats"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/dashboard");
      if (error) throw error;
      return data;
    },
  });
}

function useTaStats() {
  return useQuery({
    queryKey: ["dashboard", "ta-stats"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/ta/stats");
      if (error) throw error;
      return data as unknown as TaStats;
    },
  });
}

/**
 * Port `legacy/static/js/newsroom/dashboard.js` + `tab_dashboard.html`.
 * 2 fetch paralel (`/api/dashboard`, `/api/ta/stats`) jadi 2 `useQuery`
 * independen (bukan `Promise.all` kayak lama) -- tiap section render
 * begitu datanya sendiri siap, gak nunggu yang paling lambat.
 *
 * Scraper Health widget (§Scraper Health lama, accept-rate chart + tabel
 * per-script) SENGAJA GAK diport ke sini walau `/api/scraper/health` udah
 * ada (Fase 9) -- keputusan user (2026-09-25): control plane scraper
 * dapet halaman SENDIRI (`/scrapers`), bukan digabung ke dashboard umum.
 */
export default function DashboardPage() {
  const dashboard = useDashboardStats();
  const ta = useTaStats();

  return (
    <div className="space-y-1 pb-10">
      <header className="mb-6">
        <div className="text-sm text-muted-foreground">Ringkasan intelijen</div>
        <h1 className="font-heading text-3xl font-extrabold tracking-tight text-foreground">Dashboard</h1>
      </header>

      <AttentionBand />

      {/* ── KPI ── */}
      {(dashboard.isPending || ta.isPending) && <StatGridSkeleton count={4} />}
      {dashboard.isError && <ErrorNote />}
      {dashboard.data && ta.data && (
        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatBox
            label="Total Articles"
            value={dashboard.data.total_articles}
            sub="In database"
            spark={dashboard.data.timeline.map((x) => x.count)}
          />
          <StatBox label="Countries Mentioned" value={dashboard.data.total_countries} sub="Unique geographies" />
          <StatBox
            label="Threat Actors Tracked"
            value={dashboard.data.total_threat_actors}
            sub={`${ta.data.total_groups.toLocaleString()} APT groups · ${ta.data.total_whitelisted} whitelisted`}
          />
          <StatBox
            label="Covered in News"
            value={ta.data.in_news_count}
            sub={`${ta.data.manual_count} added manually`}
          />
        </div>
      )}

      {/* ── News Intelligence charts ── */}
      <DashboardSectionLabel>News Intelligence</DashboardSectionLabel>
      {dashboard.data && (
        <div className="space-y-3">
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <MapCard title="Mentioned Countries">
              <CountryMap data={dashboard.data.country_counts} />
            </MapCard>
            <MapCard title="Articles by News Type">
              <BreakdownList items={dashboard.data.by_news_type.map((x) => ({ label: toTitleCase(x.name), count: x.count }))} limit={9} />
            </MapCard>
          </div>

          <ChartCard title="Articles Over Time" height={200}>
            <TimelineChart
              labels={dashboard.data.timeline.map((x) => x.date)}
              data={dashboard.data.timeline.map((x) => x.count)}
            />
          </ChartCard>

          <ChartCard title="Top Threat Actors" height={280}>
            <HorizontalBarChart
              labels={dashboard.data.top_threat_actors.map((x) => toTitleCase(x.name))}
              data={dashboard.data.top_threat_actors.map((x) => x.count)}
              tone="critical"
            />
          </ChartCard>

          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <ChartCard title="Top Targeted Industries" height={280}>
              <HorizontalBarChart
                labels={dashboard.data.top_industries.map((x) => toTitleCase(x.name))}
                data={dashboard.data.top_industries.map((x) => x.count)}
                tone="warning"
              />
            </ChartCard>
            <ChartCard title="Top MITRE ATT&CK TTPs" height={280}>
              <HorizontalBarChart
                labels={dashboard.data.top_ttps.map((x) => toTitleCase(x.name))}
                data={dashboard.data.top_ttps.map((x) => x.count)}
                tone="success"
              />
            </ChartCard>
          </div>
        </div>
      )}

      {/* ── Threat Actor Room charts ── */}
      <DashboardSectionLabel>Threat Actor Room — Charts</DashboardSectionLabel>
      {ta.data && (
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          <MapCard title="APT Groups by Source">
            <BreakdownList items={ta.data.by_source.map((x) => ({ label: toTitleCase(x.name), count: x.count }))} />
          </MapCard>
          <ChartCard title="Tracked APT Groups — News Mentions" height={260}>
            {ta.data.top_in_news.length ? (
              <HorizontalBarChart
                labels={ta.data.top_in_news.map((x) => toTitleCase(x.name))}
                data={ta.data.top_in_news.map((x) => x.count)}
                tone="success"
              />
            ) : (
              <p className="flex h-full items-center justify-center text-xs text-muted-foreground">
                No tracked groups mentioned yet.
              </p>
            )}
          </ChartCard>
        </div>
      )}

    </div>
  );
}

function StatGridSkeleton({ count }: { count: number }) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {Array.from({ length: count }, (_, i) => (
        <Skeleton key={i} className="h-20 w-full" />
      ))}
    </div>
  );
}

function ErrorNote() {
  return <p className="text-sm text-destructive">Failed to load dashboard data.</p>;
}
