import { useCallback, useEffect, useRef, useState } from "react";

import { checkHealth, type HealthResult } from "../api/health";

/** Runs the health check on mount and whenever `refresh` is called. */
export function useHealth() {
  const [result, setResult] = useState<HealthResult | null>(null);
  const [checking, setChecking] = useState(false);
  const inFlight = useRef<AbortController | null>(null);

  const refresh = useCallback(async () => {
    inFlight.current?.abort();
    const controller = new AbortController();
    inFlight.current = controller;
    setChecking(true);
    const next = await checkHealth(controller.signal);
    if (!controller.signal.aborted) {
      setResult(next);
      setChecking(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    return () => inFlight.current?.abort();
  }, [refresh]);

  return { result, checking, refresh };
}
