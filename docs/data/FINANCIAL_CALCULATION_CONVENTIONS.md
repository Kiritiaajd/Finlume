# Financial Calculation Conventions

The rules every Finlume calculation follows. Sections marked **Implemented** describe code
that exists in `backend/domain/` today and is covered by tests in `backend/tests/domain/`.
Sections marked **MVP** or **Future** describe planned behaviour.

If this document and the code disagree, that is a bug: fix one of them in the same pull
request. Any change to these conventions that can alter a calculated output also requires an
[engine version](#10-reproducibility-and-versioning) bump.

## 1. Principles

1. **Deterministic.** The same inputs and the same engine version always give the same outputs, independent of machine, locale, time or ambient decimal context.
2. **Pure.** Calculations are ordinary Python functions in `backend/domain/`, with no Django, database, network or file access. `tests/test_architecture.py` enforces this.
3. **Exact money.** Monetary values are `decimal.Decimal`. Floats are rejected with a `TypeError`, and NaN and infinities with a `ValueError` (`ensure_finite_decimal`).
4. **Explicit, never assumed.** Currency, period, scale, sign and rounding are always explicit. A missing value is never treated as zero.
5. **Explainable.** Every result carries a stable code, its methodology text, the input values used, and any issues.
6. **AI does not do arithmetic.** Future AI features (Phase 3) can only explain stored results. They never compute, estimate or invent figures.

## 2. Module map (Implemented)

| Module | Responsibility |
|--------|----------------|
| `domain.financial_statements.units` | `Currency`, `Scale`, `normalize_amount`, `ensure_finite_decimal` |
| `domain.financial_statements.periods` | `PeriodType`, `ReportingPeriod` |
| `domain.financial_statements.line_items` | `StatementType`, `LineItem` taxonomy, sign-convention sets |
| `domain.financial_statements.facts` | `FinancialFactSet`: the engine's only input |
| `domain.validation` | `Severity`, `IssueCode`, `Issue`, consistency checks |
| `domain.calculations.precision` | `CALCULATION_CONTEXT`, `quantize_result` |
| `domain.calculations.metrics` | `RatioDefinition`, `MetricResult`, `compute_ratio`, `RATIO_DEFINITIONS` |
| `domain.calculations.analysis` | `run_statement_analysis` → `AnalysisOutcome` |
| `domain.calculations.version` | `ENGINE_VERSION` |

Dependency direction inside the domain: `financial_statements` ← `validation` ← `calculations`.

## 3. Currencies, scales and periods (Implemented)

### Currency

`Currency(code)` accepts any three-uppercase-letter code that has the ISO 4217 alphabetic
shape (`USD`, `INR`, `EUR`). Whether a code is supported is decided at the input boundary
(MVP API). A `FinancialFactSet` has exactly **one** currency. The engine never combines
currencies and performs **no FX conversion**. FX policy is unresolved decision D-03.

### Scale

Source documents report figures in a scale. Each `Scale` value is a power of ten:

| `Scale` | Exponent | Multiplier |
|---------|----------|------------|
| `UNITS` | 0 | 1 |
| `THOUSANDS` | 3 | 1,000 |
| `LAKHS` | 5 | 100,000 |
| `MILLIONS` | 6 | 1,000,000 |
| `CRORES` | 7 | 10,000,000 |
| `BILLIONS` | 9 | 1,000,000,000 |

`normalize_amount(amount, scale)` converts to base currency units with `Decimal.scaleb` in a
private context of 100 digits that **traps `Inexact`**. Scaling is therefore exact, and if it
ever could not be exact it would raise an error rather than round. It does not depend on the
caller's decimal context. Example: `normalize_amount(Decimal("3.25"), Scale.LAKHS) ==
Decimal("325000")`.

Raw `reported_amount` values keep their reported scale. Normalised `FinancialFact` values are
always in base units (see the [data model](DATA_MODEL.md#48-financialfact-implemented)).

### Reporting period

`ReportingPeriod(start, end, period_type)` with `start <= end` (enforced). `PeriodType` is
one of `annual`, `half_year`, `quarter`, `month` or `other`.

- Flow statements (income statement, cash flow) cover `start`..`end` inclusive.
- Balance sheet figures are a position **as of** `end` (`ReportingPeriod.as_of`).
- One `FinancialFactSet` describes one period. Ratios that mix a flow with a position (ROE, ROA) use the closing balance of the same period (see §6).
- A stored balance sheet carries the period it closes: the same start, end and type as the income statement. Assembly (rule A2, `services.statement_analysis`) combines the validated income statement, balance sheet and cash flow of one entity and one period into one `FinancialFactSet`, using confirmed facts only and one currency ([data model §6](DATA_MODEL.md#6-handling-financial-data-specifics)).

## 4. Line-item taxonomy (Implemented)

`LineItem` defines 21 canonical codes. Codes are persisted and exposed in the API: they are
never renamed or reused.

| Statement | Code | Sign convention |
|-----------|------|-----------------|
| Income statement | `revenue` | ≥ 0 |
| | `cost_of_revenue` | ≥ 0 (expense as a positive magnitude) |
| | `gross_profit` | signed |
| | `operating_expenses` | ≥ 0 |
| | `operating_income` | signed |
| | `interest_expense` | ≥ 0 |
| | `income_before_tax` | signed |
| | `income_tax_expense` | signed (a tax benefit can be negative) |
| | `net_income` | signed (a loss is negative) |
| Balance sheet | `cash_and_cash_equivalents` | ≥ 0 |
| | `inventories` | ≥ 0 |
| | `total_current_assets` | ≥ 0 |
| | `total_assets` | ≥ 0 |
| | `total_current_liabilities` | ≥ 0 |
| | `total_liabilities` | ≥ 0 |
| | `total_debt` | ≥ 0 |
| | `total_equity` | signed (can be negative) |
| Cash flow | `net_cash_from_operating_activities` | signed |
| | `capital_expenditure` | ≤ 0 (cash outflow) |
| | `net_cash_from_investing_activities` | signed |
| | `net_cash_from_financing_activities` | signed |

The "≥ 0" codes form `NON_NEGATIVE_ITEMS` and `capital_expenditure` forms
`NON_POSITIVE_ITEMS` in `line_items.py`. Input that breaks the convention is **flagged, not
flipped**. Converting a source's sign convention (for example, expenses shown in parentheses)
is the job of the ingestion mapping step (MVP), and the raw text is kept in
`StatementLineItem.raw_value`.

Mapping IFRS, US GAAP and Ind AS labels and supporting user-defined line items is
unresolved decision D-05.

## 5. Missing data (Implemented)

- `FinancialFactSet` holds only the facts that exist. `facts.get(item)` returns `None` for an absent item. `None` and `0` are different: zero is a reported value, absence is unknown.
- A metric with a missing input returns `value = None` and a `missing_input` issue listing the missing line items. Its `inputs` contain only the values that were present.
- Validation checks that need an absent value are **skipped**, not failed. The missing value surfaces through the metrics that need it.
- Values are never interpolated, carried forward or estimated.

## 6. Metrics (Implemented — engine 0.1.0)

All MVP metrics are ratios (`MetricUnit.RATIO`). Margins and returns are stored as ratios:
`0.25` means 25 %. Converting to a percentage is a presentation concern.

| Code | Formula | Warn on negative denominator | Methodology (stored with each result) |
|------|---------|------------------------------|----------------------------------------|
| `gross_margin` | `gross_profit / revenue` | No | Reported gross profit divided by revenue for the same period. |
| `operating_margin` | `operating_income / revenue` | No | Operating income divided by revenue for the same period. |
| `net_margin` | `net_income / revenue` | No | Net income divided by revenue for the same period. |
| `current_ratio` | `total_current_assets / total_current_liabilities` | No | Total current assets divided by total current liabilities at period end. |
| `debt_to_equity` | `total_debt / total_equity` | **Yes** | Total debt divided by total equity at period end. |
| `return_on_equity` | `net_income / total_equity` | **Yes** | Net income for the period divided by closing total equity. Uses closing rather than average equity because only one period is analysed. |
| `return_on_assets` | `net_income / total_assets` | No | Net income for the period divided by closing total assets. Uses closing rather than average assets because only one period is analysed. |

Notes:

- `gross_margin` uses the **reported** `gross_profit`. It does not derive gross profit from revenue minus cost of revenue. A disagreement between the two is reported by the `subtotal_mismatch` check (§8).
- Average-balance variants (average equity or assets across two periods) need multi-period support (unresolved decision D-06). They will be **new** metric codes, not changes to these ones.
- `RATIO_DEFINITIONS` fixes the order of metrics in reports. Metric codes are unique, and a test enforces this.

### Edge cases

| Situation | Result |
|-----------|--------|
| Numerator or denominator missing | `value = None`, issue `missing_input` (warning) |
| Denominator exactly zero | `value = None`, issue `zero_denominator` (warning). Never infinity and never an exception |
| Denominator negative, for a metric flagged "warn" | Value is computed, plus issue `negative_denominator` (warning), because the ratio is not meaningful |
| Denominator negative, for other metrics | Value is computed. Sign-convention validation flags a negative value for a non-negative item |
| Magnitude of the result at least `1E+18` (`MAX_RESULT_ABS`), for example a tiny denominator | `value = None`, issue `result_out_of_range` (warning). Never an exception. The bound keeps every stored result within `numeric(24,6)` |
| Numerator negative (a loss) | Value is computed and negative. Not an issue |

## 7. Precision and rounding (Implemented)

| Rule | Value | Where |
|------|-------|-------|
| Calculation context | `prec=34`, `rounding=ROUND_HALF_EVEN`, traps `InvalidOperation`, `DivisionByZero`, `Overflow` | `CALCULATION_CONTEXT` in `precision.py` |
| Context isolation | Every calculation runs inside `localcontext(CALCULATION_CONTEXT)`. Results are identical even if the caller changed the thread's context (tested) | `compute_ratio` |
| Stored result precision | 6 decimal places, round half to even (banker's rounding) | `quantize_result`, `RESULT_DECIMAL_PLACES = 6` |
| Storage type | `numeric(24,6)` for metric results; `numeric(30,6)` for amounts | [Database conventions](DATABASE_CONVENTIONS.md#data-types) |
| Input precision | Inputs are used exactly as given. Scaling is exact (§3) | |
| Display rounding | Only in clients (for example, a 0.123457 ratio shown as "12.3 %"). Never stored, and never fed back into calculations | MVP web app |

Examples from the tests: `1 / 3` → `0.333333`; `2.0000005 / 1` → `2.000000` (half-even
midpoint).

Rounding happens **once**, at the end of each metric. Intermediate values are never
rounded. Future multi-step metrics must compute in full precision and quantise only the
final result.

## 8. Validation and reconciliation (Implemented)

Validation **reports** problems. It never changes data and never blocks the analysis.
`run_statement_analysis` returns validation issues alongside the metrics, and the reviewer
decides.

| Check | Rule | Tolerance | Issue code |
|-------|------|-----------|------------|
| Sign convention | Items in `NON_NEGATIVE_ITEMS` must be ≥ 0; `capital_expenditure` must be ≤ 0 | — | `unexpected_sign` |
| Balance sheet identity | `total_assets = total_liabilities + total_equity` | Flagged when the absolute difference is greater than 0.1 % of the absolute value of `total_assets` | `balance_sheet_imbalance` |
| Gross profit subtotal | `gross_profit = revenue − cost_of_revenue` | Flagged when the absolute difference is greater than 0.1 % of the absolute value of `revenue` | `subtotal_mismatch` |

- The tolerance is `DEFAULT_RELATIVE_TOLERANCE = Decimal("0.001")`. It exists because published statements are rounded, often to thousands. A difference exactly at the tolerance is **not** flagged (strict `>`).
- If an input is missing, the check is skipped.
- Checks run in a fixed order (signs, identity, subtotal), so the issue order is deterministic.

### Issue model

`Issue(code, severity, message, line_items)`:

| Severity | Meaning |
|----------|---------|
| `info` | Context only |
| `warning` | The result is usable but should be reviewed. All current checks and metric issues use this level |
| `error` | The input cannot be analysed until it is corrected. Reserved for input-boundary validation (MVP), such as a statement mixing currencies |

Issue codes (`IssueCode`) are stable API values: `missing_input`, `zero_denominator`,
`negative_denominator`, `unexpected_sign`, `balance_sheet_imbalance`,
`subtotal_mismatch` and `result_out_of_range`. The message text is for people and may be improved without a code
change. Message wording changes still bump the engine's PATCH version (§10), because the
messages are stored with the results.

## 9. Restatements (MVP)

The engine itself is stateless. The persistence layer guarantees that:

- an analysis runs on the facts of one specific statement version for each statement type;
- a restated statement (new version) never changes earlier runs, because they keep links to the facts they used;
- analysing a restated period creates a new run. The dashboard shows when a run is based on a superseded version.

See [Data lifecycle](DATA_LIFECYCLE_AND_RETENTION.md#4-restatements-and-corrections).

## 10. Reproducibility and versioning

### Engine version (Implemented)

`domain.calculations.version.ENGINE_VERSION` (currently **`0.1.0`**) is included in every
`AnalysisOutcome` and will be stored on every `AnalysisRun`. Bump it whenever a change could
alter any calculated value, issue or methodology text for the same input:

| Bump | When |
|------|------|
| MAJOR | A metric is removed or redefined incompatibly (same code, different meaning) |
| MINOR | A new metric, a changed formula or tolerance, or a new validation check |
| PATCH | A fix that changes output, including issue or methodology wording |

Each bump is recorded in `CHANGELOG.md`. Refactors that cannot change output do not bump the
version, and the existing tests must prove that.

The policy applies from the first release. Before then, `0.1.0` is unreleased and no result
has ever been persisted, so pre-release fixes amend `0.1.0` and are listed under
**Unreleased** in the changelog. Examples are the `result_out_of_range` handling and the
pluralised `missing_input` message.

### Input fingerprint (MVP, designed)

`AnalysisRun.input_fingerprint` is the SHA-256 (lowercase hex) of a canonical UTF-8 JSON
document:

```json
{
  "currency": "INR",
  "period": {"start": "2025-04-01", "end": "2026-03-31", "type": "annual"},
  "facts": [["net_income", "1250000.000000"], ["revenue", "98000000.000000"]]
}
```

- `facts` are sorted by line-item code. Values are formatted as fixed-point strings with exactly 6 decimal places (no exponent).
- Keys are sorted, there is no insignificant whitespace (`separators=(",", ":")`), and the document is ASCII-only.
- The engine version is stored separately, not hashed. The same fingerprint with the same engine version must produce identical results, and the MVP test suite will verify this end to end.

## 11. Testing calculations

Every metric or check needs tests for:

- a hand-calculated expected value from fictional figures;
- a missing input, a zero denominator, and a negative denominator where relevant;
- the rounding boundary, if the metric can produce midpoint values;
- determinism: repeated runs are equal, and results do not depend on the caller's decimal context.

The current suite lives in `backend/tests/domain/`. The calculation checklist in the
pull-request template applies to every change under `backend/domain/calculations/`.
