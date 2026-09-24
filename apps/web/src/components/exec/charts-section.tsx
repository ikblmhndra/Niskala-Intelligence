import { ChartCard } from "@/components/dashboard/stat-box";
import { DoughnutChart, GradedDoughnutChart, MultiLineChart, StackedBarChart } from "@/components/dashboard/charts";
import type { ExecDashboardV2 } from "@/lib/api/loose-types";

function toTitleCase(s: string): string {
  return s.replace(/\w\S*/g, (w) => w.charAt(0).toUpperCase() + w.slice(1));
}

/** Port 6 chart Chart.js (`exec.js` §sector/country/newstype/
 * newstype-trend/victim-country/sr-spread). SR spread role-gated lewat
 * `view_config.sections.source_reliability_spread`. */
export function ExecChartsSection({ d }: { d: ExecDashboardV2 }) {
  const showSrSpread = d.view_config.sections.source_reliability_spread && Object.keys(d.source_reliability_spread).length > 0;

  return (
    <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
      <ChartCard title="Sector Trend" height={260}>
        <MultiLineChart
          labels={d.months}
          series={d.sector_trend.map((s) => ({ label: toTitleCase(s.sector), data: s.data }))}
        />
      </ChartCard>
      <ChartCard title="Country Trend" height={260}>
        <MultiLineChart
          labels={d.months}
          series={d.country_trend.map((c) => ({ label: toTitleCase(c.country), data: c.data }))}
        />
      </ChartCard>
      {d.news_type_breakdown.length > 0 && (
        <ChartCard title="Incident Type Breakdown" height={260}>
          <DoughnutChart
            labels={d.news_type_breakdown.map((x) => x.name)}
            data={d.news_type_breakdown.map((x) => x.count)}
          />
        </ChartCard>
      )}
      {d.newstype_trend.series.length > 0 && (
        <ChartCard title="Incident Type — Monthly Trend" height={260}>
          <StackedBarChart
            labels={d.newstype_trend.months}
            series={d.newstype_trend.series.map((s) => ({ label: toTitleCase(s.type), data: s.data }))}
          />
        </ChartCard>
      )}
      <ChartCard title="Victim Country Trend" height={260}>
        {d.victim_country_trend.length > 0 ? (
          <MultiLineChart
            labels={d.months}
            series={d.victim_country_trend.map((c) => ({ label: toTitleCase(c.country), data: c.data }))}
          />
        ) : (
          <div className="flex h-full items-center justify-center font-mono text-xs text-muted-foreground">
            No victim_countries data in this period
          </div>
        )}
      </ChartCard>
      {showSrSpread && (
        <ChartCard title="Source Reliability Spread" height={260}>
          <GradedDoughnutChart counts={d.source_reliability_spread} />
        </ChartCard>
      )}
    </div>
  );
}
