import { useMemo, useState } from "react";

import { EChart, type EChartOption } from "@/components/charts/EChart";
import { type ChartPalette, chartPalettes } from "@/components/charts/palette";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatAmount, formatRatio } from "@/lib/format";
import { usePreferences } from "@/lib/preferences-context";

import { SAMPLE_COMPANY, SAMPLE_YEARS } from "./sampleData";

type Metric = "revenue" | "grossProfit" | "operatingIncome" | "netIncome";

const AMOUNT_SERIES: { key: Metric; label: string }[] = [
  { key: "revenue", label: "Revenue" },
  { key: "grossProfit", label: "Gross profit" },
  { key: "operatingIncome", label: "Operating income" },
  { key: "netIncome", label: "Net income" },
];

const MARGIN_SERIES = [
  { key: "grossMargin", label: "Gross margin" },
  { key: "operatingMargin", label: "Operating margin" },
  { key: "netMargin", label: "Net margin" },
] as const;

function baseOption(palette: ChartPalette): EChartOption {
  return {
    color: [...palette.series],
    textStyle: { color: palette.text },
    grid: { left: 8, right: 16, top: 40, bottom: 8, containLabel: true },
    legend: { top: 0, textStyle: { color: palette.text } },
    tooltip: {
      trigger: "axis",
      backgroundColor: palette.tooltipBackground,
      borderColor: palette.tooltipBorder,
      textStyle: { color: palette.tooltipText },
    },
    aria: { enabled: true },
    xAxis: {
      type: "category",
      data: SAMPLE_YEARS.map((year) => year.fiscalYear),
      axisLine: { lineStyle: { color: palette.axis } },
      axisTick: { show: false },
    },
  };
}

// Charts need numbers to draw; exact values stay in the strings shown in the
// data tables and tooltips.
const plot = (value: string) => Number(value);

function AmountsChart({ chartType }: { chartType: "bar" | "line" }) {
  const { preferences, resolvedTheme } = usePreferences();
  const palette = chartPalettes[resolvedTheme];
  const option = useMemo<EChartOption>(
    () => ({
      ...baseOption(palette),
      tooltip: {
        ...(baseOption(palette).tooltip as object),
        valueFormatter: (value: unknown) =>
          typeof value === "number" ? formatAmount(String(value), preferences.locale) : "–",
      },
      yAxis: {
        type: "value",
        axisLabel: {
          color: palette.text,
          formatter: (value: number) => formatAmount(String(value), preferences.locale),
        },
        splitLine: { lineStyle: { color: palette.splitLine } },
      },
      series: AMOUNT_SERIES.map(({ key, label }) => ({
        name: label,
        type: chartType,
        smooth: chartType === "line",
        emphasis: { focus: "series" },
        data: SAMPLE_YEARS.map((year) => plot(year[key])),
      })),
    }),
    [chartType, palette, preferences.locale],
  );
  return (
    <EChart
      option={option}
      ariaLabel={`Sample ${chartType} chart of revenue, gross profit, operating income and net income from FY2021 to FY2025, in ${SAMPLE_COMPANY.currency} ${SAMPLE_COMPANY.scaleLabel}.`}
    />
  );
}

function MarginsChart() {
  const { preferences, resolvedTheme } = usePreferences();
  const palette = chartPalettes[resolvedTheme];
  const option = useMemo<EChartOption>(
    () => ({
      ...baseOption(palette),
      tooltip: {
        ...(baseOption(palette).tooltip as object),
        valueFormatter: (value: unknown) =>
          typeof value === "number"
            ? formatRatio(value.toFixed(6), preferences.locale, preferences.ratioDisplay)
            : "–",
      },
      yAxis: {
        type: "value",
        min: 0,
        axisLabel: {
          color: palette.text,
          formatter: (value: number) =>
            formatRatio(value.toFixed(6), preferences.locale, preferences.ratioDisplay),
        },
        splitLine: { lineStyle: { color: palette.splitLine } },
      },
      series: MARGIN_SERIES.map(({ key, label }) => ({
        name: label,
        type: "line",
        symbolSize: 7,
        emphasis: { focus: "series" },
        data: SAMPLE_YEARS.map((year) => plot(year[key])),
      })),
    }),
    [palette, preferences.locale, preferences.ratioDisplay],
  );
  return (
    <EChart
      option={option}
      ariaLabel="Sample line chart of gross, operating and net margin from FY2021 to FY2025."
    />
  );
}

export function SampleAmountsCard() {
  const [chartType, setChartType] = useState<"bar" | "line">("bar");
  const { preferences } = usePreferences();

  return (
    <Card>
      <CardHeader className="flex-row flex-wrap items-start justify-between gap-3">
        <div className="space-y-1.5">
          <CardTitle>Income statement trend</CardTitle>
          <CardDescription>
            {SAMPLE_COMPANY.currency}, {SAMPLE_COMPANY.scaleLabel}. Click a legend entry to hide
            or show a series.
          </CardDescription>
        </div>
        <div className="inline-flex rounded-md border p-0.5" role="group" aria-label="Chart type">
          {(["bar", "line"] as const).map((type) => (
            <Button
              key={type}
              size="sm"
              variant={chartType === type ? "secondary" : "ghost"}
              aria-pressed={chartType === type}
              onClick={() => setChartType(type)}
              className="h-7 capitalize"
            >
              {type}
            </Button>
          ))}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <AmountsChart chartType={chartType} />
        <DataTable
          caption={`Sample income statement figures (${SAMPLE_COMPANY.currency}, ${SAMPLE_COMPANY.scaleLabel})`}
          columns={AMOUNT_SERIES.map((series) => series.label)}
          rows={SAMPLE_YEARS.map((year) => ({
            label: year.fiscalYear,
            cells: AMOUNT_SERIES.map(({ key }) => formatAmount(year[key], preferences.locale)),
          }))}
        />
      </CardContent>
    </Card>
  );
}

export function SampleMarginsCard() {
  const { preferences } = usePreferences();
  return (
    <Card>
      <CardHeader>
        <CardTitle>Margins</CardTitle>
        <CardDescription>
          {`Ratios to revenue, shown as ${
            preferences.ratioDisplay === "percent" ? "percentages" : "decimals"
          }. Change this in Settings.`}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <MarginsChart />
        <DataTable
          caption="Sample margins"
          columns={MARGIN_SERIES.map((series) => series.label)}
          rows={SAMPLE_YEARS.map((year) => ({
            label: year.fiscalYear,
            cells: MARGIN_SERIES.map(({ key }) =>
              formatRatio(year[key], preferences.locale, preferences.ratioDisplay),
            ),
          }))}
        />
      </CardContent>
    </Card>
  );
}

interface DataTableProps {
  caption: string;
  columns: string[];
  rows: { label: string; cells: string[] }[];
}

/** The accessible, exact-value alternative to each chart. */
function DataTable({ caption, columns, rows }: DataTableProps) {
  return (
    <details className="group rounded-md border">
      <summary className="cursor-pointer select-none px-3 py-2 text-sm font-medium text-muted-foreground hover:text-foreground">
        Show data table
      </summary>
      <div className="overflow-x-auto border-t">
        <table className="w-full text-sm">
          <caption className="sr-only">{caption}</caption>
          <thead>
            <tr className="text-muted-foreground">
              <th scope="col" className="px-3 py-2 text-left font-medium">
                Year
              </th>
              {columns.map((column) => (
                <th key={column} scope="col" className="px-3 py-2 text-right font-medium">
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.label} className="border-t">
                <th scope="row" className="px-3 py-2 text-left font-medium">
                  {row.label}
                </th>
                {row.cells.map((cell, index) => (
                  <td key={columns[index]} className="px-3 py-2 text-right tabular-nums">
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
