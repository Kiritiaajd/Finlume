import { CircleAlert } from "lucide-react";
import { isRouteErrorResponse, useRouteError } from "react-router";

import { EmptyState } from "@/components/EmptyState";
import { Button } from "@/components/ui/button";

/** Shown when rendering a page throws. Details stay in the console. */
export function RouteErrorPage() {
  const error = useRouteError();
  const message = isRouteErrorResponse(error)
    ? `${error.status} ${error.statusText}`
    : "Something went wrong while displaying this page.";

  return (
    <div className="p-6">
      <EmptyState icon={CircleAlert} title="Unexpected error" description={<p>{message}</p>}>
        <Button variant="outline" onClick={() => window.location.assign("/")}>
          Reload the dashboard
        </Button>
      </EmptyState>
    </div>
  );
}
