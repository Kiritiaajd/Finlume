import { FileText, Plus } from "lucide-react";

import { EmptyState } from "@/components/EmptyState";
import { PageHeader } from "@/components/PageHeader";
import { UnavailableAction } from "@/components/UnavailableAction";

export function ReportsPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Reports"
        description="Saved, titled views of one or more analyses, with your notes kept separate from calculated values."
        actions={
          <UnavailableAction
            icon={Plus}
            label="New report"
            reason="Not available yet: reports arrive with the analysis API (MVP step 5)."
          />
        }
      />
      <EmptyState
        icon={FileText}
        title="No reports yet"
        description={
          <p>
            Reports are built from saved analyses. Neither exists in the backend yet, so there is
            nothing to show.
          </p>
        }
      />
    </div>
  );
}
