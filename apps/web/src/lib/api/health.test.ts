import { afterEach, describe, expect, it, vi } from "vitest";

import { jsonResponse, mockFetch } from "@/test/utils";

import { ApiContractError, ApiResponseError, ApiUnavailableError } from "./errors";
import { apiStatusFrom, fetchHealth } from "./health";

afterEach(() => vi.unstubAllGlobals());

describe("fetchHealth", () => {
  it("calls the versioned health endpoint on the same origin", async () => {
    const fetchMock = mockFetch(async () =>
      jsonResponse({ status: "ok", checks: { database: "ok" } }),
    );

    await expect(fetchHealth()).resolves.toEqual({ status: "ok", checks: { database: "ok" } });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/health/",
      expect.objectContaining({ method: "GET", credentials: "same-origin" }),
    );
  });

  it("treats a 503 health body as a degraded API, not an outage", async () => {
    mockFetch(async () =>
      jsonResponse({ status: "unavailable", checks: { database: "unavailable" } }, 503),
    );

    const health = await fetchHealth();

    expect(apiStatusFrom({ data: health, error: null, isPending: false })).toEqual({
      kind: "degraded",
    });
  });

  it("reports the API as unavailable when the network request fails", async () => {
    mockFetch(async () => {
      throw new TypeError("Failed to fetch");
    });

    await expect(fetchHealth()).rejects.toBeInstanceOf(ApiUnavailableError);
  });

  it("reports the API as unavailable when the dev proxy answers with an error page", async () => {
    mockFetch(async () => new Response("Bad gateway", { status: 502 }));

    await expect(fetchHealth()).rejects.toBeInstanceOf(ApiUnavailableError);
  });

  it("rejects a 200 response that breaks the health contract", async () => {
    mockFetch(async () => jsonResponse({ status: "fine" }));

    await expect(fetchHealth()).rejects.toBeInstanceOf(ApiContractError);
  });

  it("surfaces the backend's error envelope", async () => {
    mockFetch(async () =>
      jsonResponse(
        { error: { code: "throttled", message: "Slow down.", details: null, request_id: "abc" } },
        429,
      ),
    );

    const error = await fetchHealth().catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(ApiResponseError);
    expect(error).toMatchObject({ status: 429, code: "throttled", requestId: "abc" });
  });
});

describe("apiStatusFrom", () => {
  it("is checking while the first request is pending", () => {
    expect(apiStatusFrom({ error: null, isPending: true })).toEqual({ kind: "checking" });
  });

  it("is connected when the API and database are up", () => {
    expect(
      apiStatusFrom({
        data: { status: "ok", checks: { database: "ok" } },
        error: null,
        isPending: false,
      }),
    ).toEqual({ kind: "connected" });
  });
});
