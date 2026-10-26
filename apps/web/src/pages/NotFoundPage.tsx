import { CircleOff } from "lucide-react";
import { Link } from "react-router";

import { EmptyState } from "@/components/EmptyState";
import { Button } from "@/components/ui/button";

export function NotFoundPage() {
  return (
    <EmptyState icon={CircleOff} title="Page not found" description={<p>This page does not exist.</p>}>
      <Button asChild variant="outline">
        <Link to="/">Go to the dashboard</Link>
      </Button>
    </EmptyState>
  );
}
