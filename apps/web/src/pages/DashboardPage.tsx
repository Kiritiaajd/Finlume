import { ArrowRight, CircleOff, FlaskConical, Plus } from "lucide-react";
import { lazy, Suspense, useState } from "react";

import { ApiStatusPanel } from "@/components/ApiStatus";
import { EmptyState } from "@/components/EmptyState";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { UnavailableAction } from "@/components/UnavailableAction";

// ECharts is the largest dependency; load it only when the sample is opened.
const SampleDashboard = lazy(() =>
  import("@/features/sample/SampleDashboard").then((module) => ({
    default: module.SampleDashboard,
  })),
);

function SampleDashboardFallback() {
  return (
    <div className="space-y-4" aria-busy="true" aria-label="Loading the sample dashboard">
      <Skeleton className="h-16 w-full" />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }, (_, index) => (
          <Skeleton key={index} className="h-24" />
        ))}
      </div>
      <Skeleton className="h-80 w-full" />
    </div>
  );
}

type View = "yours" | "sample";

export function DashboardPage() {
  const [view, setView] = useState<View>("yours");

  return (
    <div className="space-y-6">
      <PageHeader
        title="Dashboard"
        description="Your financial overview. Real figures appear here once you add statements; until then you can explore a clearly labelled synthetic example."
      />

      <Card>
        <CardHeader>
          <CardTitle>Backend connection</CardTitle>
        </CardHeader>
        <CardContent>
          <ApiStatusPanel />
        </CardContent>
      </Card>

      <Tabs value={view} onValueChange={(value) => setView(value as View)}>
        <TabsList aria-label="Dashboard view">
          <TabsTrigger value="yours">Your data</TabsTrigger>
          <TabsTrigger value="sample">
            <FlaskConical aria-hidden="true" />
            Sample dashboard
          </TabsTrigger>
        </TabsList>

        <TabsContent value="yours">
          <EmptyState
            icon={CircleOff}
            title="No financial data yet"
            description={
              <p>
                Statements, analyses and saved reports will appear here. Adding them needs the
                statements and analysis APIs, which the backend does not provide yet.
              </p>
            }
          >
            <UnavailableAction
              icon={Plus}
              label="Add a statement"
              reason="Not available yet: the backend has no statements API (MVP step 3)."
            />
            <Button variant="outline" onClick={() => setView("sample")}>
              Explore the sample dashboard
              <ArrowRight aria-hidden="true" />
            </Button>
          </EmptyState>
        </TabsContent>

        <TabsContent value="sample">
          <Suspense fallback={<SampleDashboardFallback />}>
            <SampleDashboard />
          </Suspense>
        </TabsContent>
      </Tabs>
    </div>
  );
}
