import { ChartLine, Play } from "lucide-react";

import { EmptyState } from "@/components/EmptyState";
import { PageHeader } from "@/components/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { UnavailableAction } from "@/components/UnavailableAction";

/**
 * Reference copy of the backend engine's metric catalogue (engine 0.1.0,
 * docs/data/FINANCIAL_CALCULATION_CONVENTIONS.md §6). It describes methods
 * only, contains no figures, and will be replaced by data from the API.
 */
const METRICS = [
  ["Gross margin", "Gross profit ÷ revenue"],
  ["Operating margin", "Operating income ÷ revenue"],
  ["Net margin", "Net income ÷ revenue"],
  ["Current ratio", "Total current assets ÷ total current liabilities"],
  ["Debt to equity", "Total debt ÷ total equity (flagged when equity is negative)"],
  ["Return on equity", "Net income ÷ closing total equity (flagged when equity is negative)"],
  ["Return on assets", "Net income ÷ closing total assets"],
] as const;

export function AnalysisPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Analysis"
        description="Run the deterministic calculation engine on validated statements and save the results with their methodology and inputs."
        actions={
          <UnavailableAction
            icon={Play}
            label="Run analysis"
            reason="Not available yet: the analysis API arrives in MVP step 5."
          />
        }
      />

      <EmptyState
        icon={ChartLine}
        title="No analyses yet"
        description={
          <p>
            Analyses need statements, and the backend does not expose the analysis API yet.
            Saved analyses will be listed here, each with its engine version.
          </p>
        }
      />

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center gap-2">
            <CardTitle>Metrics the engine computes</CardTitle>
            <Badge variant="outline">Engine 0.1.0 · reference</Badge>
          </div>
          <CardDescription>
            Formulas only, copied from the backend's calculation conventions. A missing input or a
            zero denominator is reported as "not computable", never as zero. Results will come
            from the API, not from this page.
          </CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-muted-foreground">
                <th scope="col" className="py-2 pr-4 font-medium">
                  Metric
                </th>
                <th scope="col" className="py-2 font-medium">
                  Formula
                </th>
              </tr>
            </thead>
            <tbody>
              {METRICS.map(([name, formula]) => (
                <tr key={name} className="border-t">
                  <th scope="row" className="py-2 pr-4 text-left font-medium">
                    {name}
                  </th>
                  <td className="py-2 text-muted-foreground">{formula}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}
