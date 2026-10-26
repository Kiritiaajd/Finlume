import type { ResolverOptions } from "react-hook-form";
import { describe, expect, it } from "vitest";
import { z } from "zod";

import { zodResolver } from "./zod-resolver";

const schema = z.object({
  currency: z.string().regex(/^[A-Z]{3}$/, "Use a three-letter ISO 4217 code."),
  period: z.object({ year: z.number().int().min(1900, "Too early.") }),
});
type Values = z.infer<typeof schema>;

const options = {
  fields: {},
  shouldUseNativeValidation: false,
} as ResolverOptions<Values>;

describe("zodResolver", () => {
  it("returns parsed values and no errors for valid input", async () => {
    const resolve = zodResolver(schema);

    const result = await resolve({ currency: "INR", period: { year: 2025 } }, undefined, options);

    expect(result).toEqual({ values: { currency: "INR", period: { year: 2025 } }, errors: {} });
  });

  it("maps issues to nested field errors", async () => {
    const resolve = zodResolver(schema);

    const result = await resolve({ currency: "inr", period: { year: 1800 } }, undefined, options);

    expect(result.values).toEqual({});
    expect(result.errors).toEqual({
      currency: { type: "invalid_format", message: "Use a three-letter ISO 4217 code." },
      period: { year: { type: "too_small", message: "Too early." } },
    });
  });
});
