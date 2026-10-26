import { FlaskConical } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

export function SampleDataNotice() {
  return (
    <Alert variant="warning">
      <FlaskConical aria-hidden="true" />
      <AlertTitle>Synthetic sample data</AlertTitle>
      <AlertDescription>
        <p>
          Invented figures for a fictional company, bundled with the web app to demonstrate the
          dashboard. They are not loaded from the backend, not calculated by the Finlume engine,
          and do not describe any real business.
        </p>
      </AlertDescription>
    </Alert>
  );
}
