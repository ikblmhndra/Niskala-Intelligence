"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import type { TaStats } from "@/lib/api/loose-types";
import { ChartCard, DashboardSectionLabel, StatBox } from "@/components/dashboard/stat-box";
import { DoughnutChart, HorizontalBarChart, TimelineChart } from "@/components/dashboard/charts";
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
      {/* ── News Intelligence stat boxes ── */}
      {dashboard.isPending && <StatGridSkeleton count={3} />}
      {dashboard.isError && <ErrorNote />}
      {dashboard.data && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <StatBox label="Total Articles" value={dashboard.data.total_articles} sub="In database" />
          <StatBox
            label="Countries Mentioned"
            value={dashboard.data.total_countries}
            sub="Unique geographies"
          />
          <StatBox
            label="Threat Actors Tracked"
            value={dashboard.data.total_threat_actors}
            sub="Known groups & APTs"
          />
        </div>
      )}

      {/* ── Threat Actor Intelligence stat boxes ── */}
      <DashboardSectionLabel>Threat Actor Intelligence</DashboardSectionLabel>
      {ta.isPending && <StatGridSkeleton count={4} />}
      {ta.isError && <ErrorNote />}
      {ta.data && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatBox label="Tracked APT Groups" value={ta.data.total_groups} sub="In Threat Actor Room" />
          <StatBox label="Whitelisted Groups" value={ta.data.total_whitelisted} sub="Removed from tracking" />
          <StatBox label="Manual Additions" value={ta.data.manual_count} sub="Manually tracked groups" />
          <StatBox label="Covered in News" value={ta.data.in_news_count} sub="Tracked groups in articles" />
        </div>
      )}

      {/* ── News Intelligence charts ── */}
      <DashboardSectionLabel>News Intelligence</DashboardSectionLabel>
      {dashboard.data && (
        <div className="space-y-3">
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <ChartCard title="Top Mentioned Countries" height={300}>
              <HorizontalBarChart
                labels={dashboard.data.top_countries.map((x) => toTitleCase(x.name))}
                data={dashboard.data.top_countries.map((x) => x.count)}
                tone="info"
              />
            </ChartCard>
            <ChartCard title="Articles by News Type" height={300}>
              <DoughnutChart
                labels={dashboard.data.by_news_type.map((x) => toTitleCase(x.name))}
                data={dashboard.data.by_news_type.map((x) => x.count)}
              />
            </ChartCard>
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
          <ChartCard title="APT Groups by Source" height={260}>
            <DoughnutChart
              labels={ta.data.by_source.map((x) => toTitleCase(x.name))}
              data={ta.data.by_source.map((x) => x.count)}
            />
          </ChartCard>
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
