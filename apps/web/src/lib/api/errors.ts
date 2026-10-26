import { z } from "zod";

/** The backend's uniform error envelope (docs/api/API_CONVENTIONS.md). */
export const errorEnvelopeSchema = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
    details: z.unknown().optional(),
    request_id: z.string().optional(),
  }),
});

/** The API could not be reached at all: server stopped, proxy failure, timeout. */
export class ApiUnavailableError extends Error {
  readonly name = "ApiUnavailableError";
  constructor(message: string, options?: { cause?: unknown }) {
    super(message, options);
  }
}

/** The API answered with a documented error envelope. */
export class ApiResponseError extends Error {
  readonly name = "ApiResponseError";
  readonly status: number;
  readonly code: string;
  readonly details: unknown;
  readonly requestId: string | undefined;

  constructor(
    status: number,
    envelope: z.infer<typeof errorEnvelopeSchema>["error"],
  ) {
    super(envelope.message);
    this.status = status;
    this.code = envelope.code;
    this.details = envelope.details;
    this.requestId = envelope.request_id;
  }
}

/** The API answered, but not in the shape this client expects. */
export class ApiContractError extends Error {
  readonly name = "ApiContractError";
  readonly status: number;
  constructor(message: string, status: number, options?: { cause?: unknown }) {
    super(message, options);
    this.status = status;
  }
}

export type ApiError = ApiUnavailableError | ApiResponseError | ApiContractError;
