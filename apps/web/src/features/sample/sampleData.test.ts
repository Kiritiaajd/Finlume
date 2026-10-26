import { describe, expect, it } from "vitest";

import { SAMPLE_YEARS } from "./sampleData";

// Test-only arithmetic: guards the hand-written sample against typos.
// Scaled integers keep the check exact (no floating point).
const micro = (ratio: string) => BigInt(ratio.replace(".", ""));

function roundedRatioMicro(numerator: string, denominator: string): bigint {
  const n = BigInt(numerator) * 10_000_000n; // one extra digit for rounding
  const q = n / BigInt(denominator);
  const remainder = q % 10n;
  const base = q / 10n;
  // half-even on the seventh digit (exact ties do not occur in this data)
  return remainder > 5n || (remainder === 5n && base % 2n === 1n) ? base + 1n : base;
}

describe("synthetic sample data", () => {
  it.each(SAMPLE_YEARS)("$fiscalYear is internally consistent", (year) => {
    expect(BigInt(year.revenue) - BigInt(year.costOfRevenue)).toBe(BigInt(year.grossProfit));
    expect(micro(year.grossMargin)).toBe(roundedRatioMicro(year.grossProfit, year.revenue));
    expect(micro(year.operatingMargin)).toBe(roundedRatioMicro(year.operatingIncome, year.revenue));
    expect(micro(year.netMargin)).toBe(roundedRatioMicro(year.netIncome, year.revenue));
  });
});
