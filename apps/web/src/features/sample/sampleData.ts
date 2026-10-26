/**
 * SYNTHETIC SAMPLE DATA — for demonstrating the dashboard only.
 *
 * Every figure here is invented for a fictional company. Nothing is loaded
 * from the backend or produced by the Finlume calculation engine, and the
 * data must never be presented as a user's or any real business's figures.
 *
 * Values mirror the API's conventions: decimal strings, amounts in the stated
 * scale, ratios as ratios (0.25 = 25 %). The margins were computed by hand
 * from the amounts and rounded half-even to six decimal places like the
 * engine; `sampleData.test.ts` checks that they agree.
 */

export const SAMPLE_COMPANY = {
  name: "Sample Company (fictional)",
  currency: "USD",
  scaleLabel: "thousands",
} as const;

export interface SampleYear {
  fiscalYear: string;
  revenue: string;
  costOfRevenue: string;
  grossProfit: string;
  operatingIncome: string;
  netIncome: string;
  grossMargin: string;
  operatingMargin: string;
  netMargin: string;
}

export const SAMPLE_YEARS: readonly SampleYear[] = [
  {
    fiscalYear: "FY2021",
    revenue: "8200",
    costOfRevenue: "4920",
    grossProfit: "3280",
    operatingIncome: "902",
    netIncome: "574",
    grossMargin: "0.400000",
    operatingMargin: "0.110000",
    netMargin: "0.070000",
  },
  {
    fiscalYear: "FY2022",
    revenue: "9450",
    costOfRevenue: "5576",
    grossProfit: "3874",
    operatingIncome: "1134",
    netIncome: "737",
    grossMargin: "0.409947",
    operatingMargin: "0.120000",
    netMargin: "0.077989",
  },
  {
    fiscalYear: "FY2023",
    revenue: "10100",
    costOfRevenue: "6060",
    grossProfit: "4040",
    operatingIncome: "1010",
    netIncome: "667",
    grossMargin: "0.400000",
    operatingMargin: "0.100000",
    netMargin: "0.066040",
  },
  {
    fiscalYear: "FY2024",
    revenue: "11800",
    costOfRevenue: "6844",
    grossProfit: "4956",
    operatingIncome: "1534",
    netIncome: "1003",
    grossMargin: "0.420000",
    operatingMargin: "0.130000",
    netMargin: "0.085000",
  },
  {
    fiscalYear: "FY2025",
    revenue: "13250",
    costOfRevenue: "7553",
    grossProfit: "5697",
    operatingIncome: "1855",
    netIncome: "1272",
    grossMargin: "0.429962",
    operatingMargin: "0.140000",
    netMargin: "0.096000",
  },
];
