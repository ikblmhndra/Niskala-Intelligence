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

/**
 * Warna literal (bukan CSS var) -- Chart.js render ke `<canvas>`, gak bisa
 * resolve `var(--x)` tanpa `getComputedStyle`. Hex sama persis dengan
 * `.dark` block di `globals.css` (app dark-only, gak ada toggle), jadi
 * chart dan UI di sekitarnya tetap konsisten. Port dari
 * `legacy/static/js/newsroom/dashboard.js`.
 */
const BORDER = "#30363D";
const TEXT_DIM = "#8B949E";
const TEXT_BRIGHT = "#E6EDF3";
const SURFACE = "#161B22";
const CHART_COLORS = [
  "#2F81F7",
  "#58A6FF",
  "#DA3633",
  "#3DC9AF",
  "#E3B341",
  "#21262D",
  "#fd79a8",
  "#30363D",
  "#55efc4",
  "#21262D",
];

ChartJS.defaults.font.family = "'IBM Plex Mono', monospace";
ChartJS.defaults.font.size = 10;
ChartJS.defaults.color = TEXT_DIM;

interface HorizontalBarChartProps {
  labels: string[];
  data: number[];
  color?: string;
}

export function HorizontalBarChart({ labels, data, color }: HorizontalBarChartProps) {
  return (
    <Bar
      data={{
        labels,
        datasets: [
          {
            data,
            backgroundColor: color ?? "rgba(47,129,247,0.25)",
            borderColor: color ?? "#2F81F7",
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
          x: { grid: { color: BORDER }, ticks: { color: TEXT_DIM } },
          y: { grid: { display: false }, ticks: { color: TEXT_BRIGHT, font: { size: 10 } } },
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
  return (
    <Doughnut
      data={{
        labels,
        datasets: [
          {
            data,
            backgroundColor: CHART_COLORS,
            borderColor: SURFACE,
            borderWidth: 2,
            hoverOffset: 6,
          },
        ],
      }}
      options={{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: "right", labels: { color: TEXT_BRIGHT, padding: 12, font: { size: 10 } } },
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

interface TimelineChartProps {
  labels: string[];
  data: number[];
}

export function TimelineChart({ labels, data }: TimelineChartProps) {
  return (
    <Line
      data={{
        labels,
        datasets: [
          {
            data,
            borderColor: "#2F81F7",
            backgroundColor: "rgba(47,129,247,0.06)",
            borderWidth: 1.5,
            pointRadius: 2,
            pointBackgroundColor: "#2F81F7",
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
          x: { grid: { color: BORDER }, ticks: { color: TEXT_DIM, maxTicksLimit: 12 } },
          y: { grid: { color: BORDER }, ticks: { color: TEXT_DIM }, beginAtZero: true },
        },
      }}
    />
  );
}
