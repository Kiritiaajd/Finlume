import { z } from "zod";

import { API_BASE_URL, API_VERSION_PATH, isApiConfigured } from "../config";

/** Response body of `GET /api/v1/health/` (backend `apps.core.views.HealthView`). */
const healthSchema = z.object({
  status: z.enum(["ok", "unavailable"]),
  checks: z.object({ database: z.enum(["ok", "unavailable"]) }),
});

export type HealthResult =
  | { kind: "not-configured" }
  | { kind: "ok" }
  /** The API answered 503: it is running but cannot reach its database. */
  | { kind: "degraded" }
  /** No usable answer: server stopped, wrong address, or network blocked. */
  | { kind: "unreachable"; detail: string }
  /** The server answered, but not with the documented health contract. */
  | { kind: "unexpected"; detail: string };

const TIMEOUT_MS = 8000;

export async function checkHealth(signal?: AbortSignal): Promise<HealthResult> {
  if (!isApiConfigured) {
    return { kind: "not-configured" };
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  const forwardAbort = () => controller.abort();
  signal?.addEventListener("abort", forwardAbort);

  try {
    const response = await fetch(`${API_BASE_URL}${API_VERSION_PATH}/health/`, {
      headers: { Accept: "application/json" },
      signal: controller.signal,
    });
    if (response.status !== 200 && response.status !== 503) {
      return { kind: "unexpected", detail: `HTTP ${response.status}` };
    }
    const parsed = healthSchema.safeParse(await response.json().catch(() => null));
    if (!parsed.success) {
      return {
        kind: response.status === 503 ? "unreachable" : "unexpected",
        detail: "The response was not the Finlume health format.",
      };
    }
    return parsed.data.status === "ok" ? { kind: "ok" } : { kind: "degraded" };
  } catch (error) {
    const timedOut = controller.signal.aborted && !signal?.aborted;
    return {
      kind: "unreachable",
      detail: timedOut ? `No response within ${TIMEOUT_MS / 1000} s.` : String(error),
    };
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", forwardAbort);
  }
}
