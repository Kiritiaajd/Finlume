import type { z } from "zod";

import { apiUrl } from "@/lib/config";

import {
  ApiContractError,
  ApiResponseError,
  ApiUnavailableError,
  errorEnvelopeSchema,
} from "./errors";

export interface GetOptions {
  /** Cancellation from the caller (TanStack Query passes one per query). */
  signal?: AbortSignal;
  timeoutMs?: number;
  /**
   * Non-2xx statuses whose body is still a valid response for this endpoint,
   * e.g. 503 from the health check, which reports a degraded state.
   */
  acceptStatuses?: readonly number[];
}

export interface ApiResult<T> {
  status: number;
  data: T;
}

const DEFAULT_TIMEOUT_MS = 10_000;

/**
 * GET a versioned API path and validate the JSON body against `schema`.
 *
 * Every failure is classified so the UI can tell "the backend is down" from
 * "the backend refused" from "the backend answered something unexpected".
 */
export async function apiGet<T>(
  path: string,
  schema: z.ZodType<T>,
  { signal, timeoutMs = DEFAULT_TIMEOUT_MS, acceptStatuses = [] }: GetOptions = {},
): Promise<ApiResult<T>> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  const forwardAbort = () => controller.abort();
  signal?.addEventListener("abort", forwardAbort);

  let response: Response;
  try {
    response = await fetch(apiUrl(path), {
      method: "GET",
      headers: { Accept: "application/json" },
      credentials: "same-origin",
      signal: controller.signal,
    });
  } catch (error) {
    if (signal?.aborted) throw error; // the caller cancelled; not an outage
    const reason = controller.signal.aborted
      ? `No response within ${timeoutMs / 1000} s.`
      : "The request could not be sent.";
    throw new ApiUnavailableError(`The Finlume API is unreachable. ${reason}`, { cause: error });
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", forwardAbort);
  }

  const isJson = response.headers.get("content-type")?.includes("application/json") ?? false;
  const body: unknown = isJson ? await response.json().catch(() => undefined) : undefined;

  if (response.ok || acceptStatuses.includes(response.status)) {
    if (body !== undefined) {
      const parsed = schema.safeParse(body);
      if (parsed.success) return { status: response.status, data: parsed.data };
      if (response.ok) {
        throw new ApiContractError(
          `Unexpected response format from ${path}.`,
          response.status,
          { cause: parsed.error },
        );
      }
    } else if (response.ok) {
      throw new ApiContractError(`Expected JSON from ${path}.`, response.status);
    }
  }

  const envelope = errorEnvelopeSchema.safeParse(body);
  if (envelope.success) {
    throw new ApiResponseError(response.status, envelope.data.error);
  }
  if (response.status >= 500) {
    // A proxy or server error page rather than a Finlume response: typically
    // the dev proxy reporting that Django is not running.
    throw new ApiUnavailableError(`The Finlume API is not responding (HTTP ${response.status}).`);
  }
  throw new ApiContractError(`Unexpected response (HTTP ${response.status}).`, response.status);
}
