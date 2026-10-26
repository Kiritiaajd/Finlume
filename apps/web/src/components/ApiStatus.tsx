import { CircleAlert, CircleCheck, LoaderCircle, RefreshCw, ServerOff, TriangleAlert } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { type ApiStatus, apiStatusFrom, useHealthQuery } from "@/lib/api/health";
import { cn } from "@/lib/utils";

const LABELS: Record<ApiStatus["kind"], string> = {
  checking: "Checking API…",
  connected: "API connected",
  degraded: "Database unavailable",
  unavailable: "API unavailable",
  error: "API error",
};

/** Compact indicator for the sidebar. */
export function ApiStatusIndicator() {
  const query = useHealthQuery();
  const status = apiStatusFrom(query);
  const tone = {
    checking: "text-muted-foreground",
    connected: "text-success",
    degraded: "text-warning",
    unavailable: "text-destructive",
    error: "text-destructive",
  }[status.kind];
  const Icon = {
    checking: LoaderCircle,
    connected: CircleCheck,
    degraded: TriangleAlert,
    unavailable: ServerOff,
    error: CircleAlert,
  }[status.kind];

  return (
    <p className={cn("flex items-center gap-2 text-xs font-medium", tone)} aria-live="polite">
      <Icon aria-hidden="true" className={cn("size-3.5", status.kind === "checking" && "animate-spin")} />
      {LABELS[status.kind]}
    </p>
  );
}

/** Full status with guidance, used on the dashboard and in settings. */
export function ApiStatusPanel() {
  const query = useHealthQuery();
  const status = apiStatusFrom(query);
  const recheck = (
    <Button
      variant="outline"
      size="sm"
      onClick={() => void query.refetch()}
      disabled={query.isFetching}
      className="mt-2 w-fit"
    >
      <RefreshCw aria-hidden="true" className={cn(query.isFetching && "animate-spin")} />
      Check again
    </Button>
  );

  switch (status.kind) {
    case "checking":
      return (
        <div className="space-y-2" aria-busy="true" aria-label="Checking the Finlume API">
          <Skeleton className="h-4 w-48" />
          <Skeleton className="h-4 w-72" />
        </div>
      );
    case "connected":
      return (
        <Alert variant="info">
          <CircleCheck aria-hidden="true" />
          <AlertTitle>Connected to the Finlume API</AlertTitle>
          <AlertDescription>
            <p>The backend and its database are reachable (GET /api/v1/health/).</p>
          </AlertDescription>
        </Alert>
      );
    case "degraded":
      return (
        <Alert variant="warning">
          <TriangleAlert aria-hidden="true" />
          <AlertTitle>The API is running, but its database is unavailable</AlertTitle>
          <AlertDescription>
            <p>Check that PostgreSQL is running and that the backend's POSTGRES_* settings are correct.</p>
            {recheck}
          </AlertDescription>
        </Alert>
      );
    case "unavailable":
      return (
        <Alert variant="destructive" role="alert">
          <ServerOff aria-hidden="true" />
          <AlertTitle>The Finlume API is unavailable</AlertTitle>
          <AlertDescription>
            <p>{status.message}</p>
            <p>
              Start the backend in another terminal:{" "}
              <code className="rounded bg-muted px-1 py-0.5 text-xs">
                cd backend; python manage.py runserver
              </code>
            </p>
            {recheck}
          </AlertDescription>
        </Alert>
      );
    case "error":
      return (
        <Alert variant="destructive" role="alert">
          <CircleAlert aria-hidden="true" />
          <AlertTitle>Unexpected response from the API</AlertTitle>
          <AlertDescription>
            <p>{status.message}</p>
            {recheck}
          </AlertDescription>
        </Alert>
      );
  }
}
