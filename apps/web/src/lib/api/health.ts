import { useQuery } from "@tanstack/react-query";
import { z } from "zod";

import { apiGet } from "./client";
import { ApiResponseError, ApiUnavailableError } from "./errors";

/** Body of `GET /api/v1/health/` (backend: `apps.core.views.HealthView`). */
export const healthSchema = z.object({
  status: z.enum(["ok", "unavailable"]),
  checks: z.object({ database: z.enum(["ok", "unavailable"]) }),
});

export type Health = z.infer<typeof healthSchema>;

export async function fetchHealth(signal?: AbortSignal): Promise<Health> {
  // 503 carries a valid body: the API is up but its database is not.
  const { data } = await apiGet("/health/", healthSchema, {
    signal,
    timeoutMs: 5_000,
    acceptStatuses: [503],
  });
  return data;
}

export const healthQueryKey = ["api", "health"] as const;

export function useHealthQuery() {
  return useQuery({
    queryKey: healthQueryKey,
    queryFn: ({ signal }) => fetchHealth(signal),
    refetchInterval: 30_000,
    staleTime: 10_000,
    retry: false,
  });
}

export type ApiStatus =
  | { kind: "checking" }
  | { kind: "connected" }
  | { kind: "degraded" }
  | { kind: "unavailable"; message: string }
  | { kind: "error"; message: string };

/** Reduce a health query to the one status the UI shows. */
export function apiStatusFrom(query: {
  data?: Health | undefined;
  error: Error | null;
  isPending: boolean;
}): ApiStatus {
  if (query.error) {
    if (query.error instanceof ApiUnavailableError) {
      return { kind: "unavailable", message: query.error.message };
    }
    const message =
      query.error instanceof ApiResponseError
        ? `${query.error.message} (${query.error.code})`
        : query.error.message;
    return { kind: "error", message };
  }
  if (query.isPending || !query.data) return { kind: "checking" };
  return query.data.status === "ok" ? { kind: "connected" } : { kind: "degraded" };
}
