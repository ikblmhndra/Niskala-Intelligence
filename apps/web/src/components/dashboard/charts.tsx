"use client";

import {
  ArcElement,
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Filler,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
  type TooltipItem,
} from "chart.js";
import { Bar, Doughnut, Line } from "react-chartjs-2";

import { useChartTheme, withAlpha } from "@/lib/chart-theme";

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  ArcElement,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
);

/** Warna dibaca dari token tema via `useChartTheme` (Chart.js render ke
 * `<canvas>`, tidak bisa resolve `var(--x)`), jadi chart ikut light/dark.
 * Port dari `legacy/static/js/newsroom/dashboard.js`. */
ChartJS.defaults.font.family = "'IBM Plex Mono', monospace";
ChartJS.defaults.font.size = 10;

interface HorizontalBarChartProps {
  labels: string[];
  data: number[];
  tone?: "primary" | "critical" | "warning" | "success";
}

export function HorizontalBarChart({ labels, data, tone = "primary" }: HorizontalBarChartProps) {
  const t = useChartTheme();
  const color = t[tone];
  return (
    <Bar
      data={{
        labels,
        datasets: [
          {
            data,
            backgroundColor: withAlpha(color, 0.4),
            borderColor: color,
            borderWidth: 1,
            borderRadius: 2,
          },
        ],
      }}
      options={{
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (ctx: TooltipItem<"bar">) => ` ${ctx.parsed.x} articles`,
            },
          },
        },
        scales: {
          x: { grid: { color: t.border }, ticks: { color: t.textDim } },
          y: { grid: { display: false }, ticks: { color: t.textBright, font: { size: 10 } } },
        },
      }}
    />
  );
}

interface DoughnutChartProps {
  labels: string[];
  data: number[];
}

export function DoughnutChart({ labels, data }: DoughnutChartProps) {
  const t = useChartTheme();
  return (
    <Doughnut
      data={{
        labels,
        datasets: [
          {
            data,
            backgroundColor: t.series,
            borderColor: t.surface,
            borderWidth: 2,
            hoverOffset: 6,
          },
        ],
      }}
      options={{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: "right", labels: { color: t.textBright, padding: 12, font: { size: 10 } } },
          tooltip: {
            callbacks: {
              label: (ctx: TooltipItem<"doughnut">) => ` ${ctx.label}: ${ctx.parsed} articles`,
            },
          },
        },
        cutout: "60%",
      }}
    />
  );
}

interface MultiLineSeries {
  label: string;
  data: number[];
}

interface MultiLineChartProps {
  labels: string[];
  series: MultiLineSeries[];
}

/** Beberapa line sekaligus 1 chart (sector/country/victim-country trend). */
export function MultiLineChart({ labels, series }: MultiLineChartProps) {
  const t = useChartTheme();
  return (
    <Line
      data={{
        labels,
        datasets: series.map((s, i) => {
          const color = t.series[i % t.series.length];
          return {
            label: s.label,
            data: s.data,
            borderColor: color,
            backgroundColor: color,
            borderWidth: 1.5,
            pointRadius: 1.5,
            tension: 0.3,
          };
        }),
      }}
      options={{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: "bottom", labels: { color: t.textDim, boxWidth: 10, font: { size: 9 } } },
          tooltip: { mode: "index", intersect: false },
        },
        scales: {
          x: { grid: { color: t.border }, ticks: { color: t.textDim, maxTicksLimit: 12 } },
          y: { grid: { color: t.border }, ticks: { color: t.textDim }, beginAtZero: true },
        },
      }}
    />
  );
}

interface StackedBarChartProps {
  labels: string[];
  series: MultiLineSeries[];
}

/** Bar stacked (news-type trend per bulan). */
export function StackedBarChart({ labels, series }: StackedBarChartProps) {
  const t = useChartTheme();
  return (
    <Bar
      data={{
        labels,
        datasets: series.map((s, i) => {
          const color = t.series[i % t.series.length];
          return {
            label: s.label,
            data: s.data,
            backgroundColor: color,
            borderWidth: 0,
          };
        }),
      }}
      options={{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: "bottom", labels: { color: t.textDim, boxWidth: 10, font: { size: 9 } } },
        },
        scales: {
          x: { stacked: true, grid: { display: false }, ticks: { color: t.textDim, maxTicksLimit: 12 } },
          y: { stacked: true, grid: { color: t.border }, ticks: { color: t.textDim } },
        },
      }}
    />
  );
}

interface TAActivityTimelineChartProps {
  labels: string[];
  articleCounts: number[];
  tweetCounts: number[];
  ransomCounts: number[];
}

/** Port `_tapLoadTimeline()`'s Chart.js config (`ta.js:740-763`) -- 3
 * series stacked+filled (Articles/Tweets/Ransom), dipakai Threat Actor
 * Room Grup G6. */
export function TAActivityTimelineChart({ labels, articleCounts, tweetCounts, ransomCounts }: TAActivityTimelineChartProps) {
  const t = useChartTheme();
  return (
    <Line
      data={{
        labels,
        datasets: [
          { label: "Articles", data: articleCounts, borderColor: withAlpha(t.primary, 0.8), backgroundColor: withAlpha(t.primary, 0.15), fill: true, tension: 0.3, pointRadius: 2 },
          { label: "Tweets", data: tweetCounts, borderColor: withAlpha(t.info, 0.8), backgroundColor: withAlpha(t.info, 0.1), fill: true, tension: 0.3, pointRadius: 2 },
          { label: "Ransom", data: ransomCounts, borderColor: withAlpha(t.critical, 0.8), backgroundColor: withAlpha(t.critical, 0.1), fill: true, tension: 0.3, pointRadius: 2 },
        ],
      }}
      options={{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: "bottom", labels: { color: t.textDim, boxWidth: 10, font: { size: 9 } } },
        },
        scales: {
          x: { grid: { color: t.border }, ticks: { color: t.textDim, maxTicksLimit: 12, font: { size: 8 } } },
          y: { grid: { color: t.border }, ticks: { color: t.textDim, font: { size: 9 } }, beginAtZero: true, stacked: true },
        },
      }}
    />
  );
}

interface GradedDoughnutChartProps {
  counts: Record<string, number>;
}

/** Doughnut Source Reliability Spread -- warna per grade A-F (bukan
 * palet siklik `CHART_COLORS`), F/grade gak dikenal fallback abu-abu. */
export function GradedDoughnutChart({ counts }: GradedDoughnutChartProps) {
  const t = useChartTheme();
  const grades = Object.keys(counts).sort();
  return (
    <Doughnut
      data={{
        labels: grades.map((g) => `${g} – ${counts[g]}`),
        datasets: [
          {
            data: grades.map((g) => counts[g]),
            backgroundColor: grades.map((g) => t.grades[g] ?? t.textDim),
            borderColor: t.surface,
            borderWidth: 2,
            hoverOffset: 6,
          },
        ],
      }}
      options={{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: "right", labels: { color: t.textBright, padding: 12, font: { size: 10 } } },
        },
        cutout: "55%",
      }}
    />
  );
}

interface TimelineChartProps {
  labels: string[];
  data: number[];
}

export function TimelineChart({ labels, data }: TimelineChartProps) {
  const t = useChartTheme();
  return (
    <Line
      data={{
        labels,
        datasets: [
          {
            data,
            borderColor: t.primary,
            backgroundColor: withAlpha(t.primary, 0.06),
            borderWidth: 1.5,
            pointRadius: 2,
            pointBackgroundColor: t.primary,
            fill: true,
            tension: 0.3,
          },
        ],
      }}
      options={{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (ctx: TooltipItem<"line">) => ` ${ctx.parsed.y} articles`,
            },
          },
        },
        scales: {
          x: { grid: { color: t.border }, ticks: { color: t.textDim, maxTicksLimit: 12 } },
          y: { grid: { color: t.border }, ticks: { color: t.textDim }, beginAtZero: true },
        },
      }}
    />
  );
}
