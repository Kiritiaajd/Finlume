import { FileSpreadsheet, Plus, Upload } from "lucide-react";

import { EmptyState } from "@/components/EmptyState";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { UnavailableAction } from "@/components/UnavailableAction";

const REQUIREMENTS = [
  ["Statement type", "Income statement, balance sheet or cash-flow statement."],
  ["Reporting period", "Start and end dates plus a period type, such as annual or quarterly."],
  ["Currency", "An ISO 4217 code such as USD or INR. One currency per statement."],
  ["Scale", "Units, thousands, lakhs, millions, crores or billions, as reported."],
  ["Line items", "Each figure mapped to Finlume's canonical line items, such as revenue or total assets."],
] as const;

export function StatementsPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Financial statements"
        description="Enter statements by hand or import them from CSV. Every figure keeps a link to where it came from."
        actions={
          <>
            <UnavailableAction
              icon={Plus}
              label="Enter statement"
              reason="Not available yet: manual entry arrives with the statements API (MVP step 3)."
            />
            <UnavailableAction
              icon={Upload}
              variant="outline"
              label="Import CSV"
              reason="Not available yet: CSV import arrives in MVP step 4."
            />
          </>
        }
      />

      <EmptyState
        icon={FileSpreadsheet}
        title="No statements yet"
        description={
          <p>
            The backend does not offer a statements API yet, so there is nothing to list. Once it
            does, your statements and their versions will appear here.
          </p>
        }
      />

      <Card>
        <CardHeader>
          <CardTitle>What each statement will record</CardTitle>
          <CardDescription>From Finlume's data model; shown for orientation only.</CardDescription>
        </CardHeader>
        <CardContent>
          <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-[12rem_1fr]">
            {REQUIREMENTS.map(([term, detail]) => (
              <div key={term} className="contents">
                <dt className="text-sm font-medium">{term}</dt>
                <dd className="text-sm text-muted-foreground">{detail}</dd>
              </div>
            ))}
          </dl>
        </CardContent>
      </Card>
    </div>
  );
}
