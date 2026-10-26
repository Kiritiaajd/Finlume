/**
 * Display formatting for financial values.
 *
 * The API sends decimals as strings (COERCE_DECIMAL_TO_STRING). They are
 * passed to Intl.NumberFormat *as strings*, which formats them exactly
 * without converting to binary floating point. This module only formats;
 * it never calculates (docs/decisions/ADR-0003).
 */

type DecimalString = `${number}`;

function asDecimalString(value: string): DecimalString {
  if (!/^-?\d+(\.\d+)?$/.test(value)) {
    throw new Error(`Not a decimal string: ${value}`);
  }
  return value as DecimalString;
}

export function formatAmount(value: string, locale: string, fractionDigits = 0): string {
  return new Intl.NumberFormat(locale, {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  }).format(asDecimalString(value));
}

export type RatioDisplay = "percent" | "decimal";

/** Ratios are stored as ratios (0.25 = 25 %); percent is presentation only. */
export function formatRatio(value: string, locale: string, display: RatioDisplay): string {
  const options: Intl.NumberFormatOptions =
    display === "percent"
      ? { style: "percent", minimumFractionDigits: 1, maximumFractionDigits: 1 }
      : { minimumFractionDigits: 2, maximumFractionDigits: 4 };
  return new Intl.NumberFormat(locale, options).format(asDecimalString(value));
}
