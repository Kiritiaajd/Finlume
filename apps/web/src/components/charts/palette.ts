/**
 * Chart colours as hex values. ECharts derives hover and emphasis shades
 * from its colours, which needs formats it can parse (not oklch).
 */
export const chartPalettes = {
  light: {
    series: ["#0f766e", "#2563eb", "#b45309", "#7c3aed"],
    text: "#475569",
    axis: "#cbd5e1",
    splitLine: "#e2e8f0",
    tooltipBackground: "#ffffff",
    tooltipBorder: "#e2e8f0",
    tooltipText: "#0f172a",
  },
  dark: {
    series: ["#2dd4bf", "#60a5fa", "#fbbf24", "#a78bfa"],
    text: "#94a3b8",
    axis: "#334155",
    splitLine: "#1e293b",
    tooltipBackground: "#111827",
    tooltipBorder: "#334155",
    tooltipText: "#e2e8f0",
  },
} as const;

export type ChartPalette = (typeof chartPalettes)[keyof typeof chartPalettes];
