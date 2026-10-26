import { describe, expect, it } from "vitest";

import { formatAmount, formatRatio } from "./format";

describe("formatAmount", () => {
  it("groups digits for the locale", () => {
    expect(formatAmount("13250", "en-US")).toBe("13,250");
    expect(formatAmount("1325000", "en-IN")).toBe("13,25,000");
  });

  it("formats decimal strings exactly, without float rounding", () => {
    // As a float, 0.1 + 0.2 style errors would show here; the string is exact.
    expect(formatAmount("12345678901234567.89", "en-US", 2)).toBe("12,345,678,901,234,567.89");
  });

  it("rejects values that are not decimal strings", () => {
    expect(() => formatAmount("1e5", "en-US")).toThrow("Not a decimal string");
  });
});

describe("formatRatio", () => {
  it("shows ratios as percentages or decimals", () => {
    expect(formatRatio("0.429962", "en-US", "percent")).toBe("43.0%");
    expect(formatRatio("0.429962", "en-US", "decimal")).toBe("0.43");
    expect(formatRatio("0.070000", "de-DE", "percent")).toBe("7,0 %");
  });
});
