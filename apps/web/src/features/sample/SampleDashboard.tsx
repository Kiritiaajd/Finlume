import { SampleDataNotice } from "@/components/SampleDataNotice";
import { Badge } from "@/components/ui/badge";
import { formatAmount, formatRatio } from "@/lib/format";
import { usePreferences } from "@/lib/preferences-context";

import { SampleAmountsCard, SampleMarginsCard } from "./SampleCharts";
import { SAMPLE_COMPANY, SAMPLE_YEARS } from "./sampleData";

export function SampleDashboard() {
  const { preferences } = usePreferences();
  const latest = SAMPLE_YEARS[SAMPLE_YEARS.length - 1];
  if (!latest) return null;

  const amount = (value: string) =>
    `${formatAmount(value, preferences.locale)} ${SAMPLE_COMPANY.currency}k`;
  const ratio = (value: string) => formatRatio(value, preferences.locale, preferences.ratioDisplay);

  const kpis = [
    { label: "Revenue", value: amount(latest.revenue) },
    { label: "Net income", value: amount(latest.netIncome) },
    { label: "Gross margin", value: ratio(latest.grossMargin) },
    { label: "Net margin", value: ratio(latest.netMargin) },
  ];

  return (
    <div className="space-y-6">
      <SampleDataNotice />

      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-lg font-semibold">{SAMPLE_COMPANY.name}</h2>
        <Badge variant="sample">Synthetic</Badge>
        <span className="text-sm text-muted-foreground">
          {latest.fiscalYear} · {SAMPLE_COMPANY.currency} {SAMPLE_COMPANY.scaleLabel}
        </span>
      </div>

      <dl className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {kpis.map((kpi) => (
          <div key={kpi.label} className="rounded-xl border bg-card p-5 shadow-xs">
            <dt className="text-sm text-muted-foreground">{kpi.label}</dt>
            <dd className="mt-2 text-2xl font-semibold tabular-nums">{kpi.value}</dd>
          </div>
        ))}
      </dl>

      <div className="grid gap-6 xl:grid-cols-2">
        <SampleAmountsCard />
        <SampleMarginsCard />
      </div>
    </div>
  );
}
