import type { LucideIcon } from "lucide-react";
import { useId } from "react";

import { Button } from "@/components/ui/button";

interface UnavailableActionProps {
  icon: LucideIcon;
  label: string;
  /** Why the action is disabled; announced to assistive technology. */
  reason: string;
  variant?: "default" | "outline";
}

/**
 * A visible but disabled action for a feature the backend does not offer
 * yet. It never fakes the feature: the reason is shown on hover and focus
 * and is read out by screen readers.
 */
export function UnavailableAction({
  icon: Icon,
  label,
  reason,
  variant = "default",
}: UnavailableActionProps) {
  const reasonId = useId();
  return (
    <span title={reason} className="inline-flex">
      <Button variant={variant} disabled aria-describedby={reasonId}>
        <Icon aria-hidden="true" />
        {label}
      </Button>
      <span id={reasonId} className="sr-only">
        {reason}
      </span>
    </span>
  );
}
