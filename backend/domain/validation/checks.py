from __future__ import annotations

from decimal import Decimal

from domain.financial_statements import FinancialFactSet, LineItem
from domain.financial_statements.line_items import NON_NEGATIVE_ITEMS, NON_POSITIVE_ITEMS

from .issues import Issue, IssueCode, Severity

#: Reported statements are rounded (often to thousands), so totals rarely tie
#: exactly. Differences within 0.1 % of the reference figure are not flagged.
DEFAULT_RELATIVE_TOLERANCE = Decimal("0.001")


def _exceeds_tolerance(difference: Decimal, reference: Decimal, tolerance: Decimal) -> bool:
    return abs(difference) > abs(reference) * tolerance


def check_sign_conventions(facts: FinancialFactSet) -> list[Issue]:
    issues: list[Issue] = []
    for item, value in facts.values.items():
        if item in NON_NEGATIVE_ITEMS and value < 0:
            expected = "zero or positive"
        elif item in NON_POSITIVE_ITEMS and value > 0:
            expected = "zero or negative"
        else:
            continue
        issues.append(
            Issue(
                IssueCode.UNEXPECTED_SIGN,
                Severity.WARNING,
                f"{item.value} is {value}; Finlume's sign convention expects it to be {expected}.",
                (item,),
            )
        )
    return issues


def check_balance_sheet_identity(
    facts: FinancialFactSet, relative_tolerance: Decimal = DEFAULT_RELATIVE_TOLERANCE
) -> list[Issue]:
    """Total assets should equal total liabilities plus total equity."""
    assets = facts.get(LineItem.TOTAL_ASSETS)
    liabilities = facts.get(LineItem.TOTAL_LIABILITIES)
    equity = facts.get(LineItem.TOTAL_EQUITY)
    if assets is None or liabilities is None or equity is None:
        return []
    difference = assets - (liabilities + equity)
    if not _exceeds_tolerance(difference, assets, relative_tolerance):
        return []
    return [
        Issue(
            IssueCode.BALANCE_SHEET_IMBALANCE,
            Severity.WARNING,
            f"Total assets differ from total liabilities plus total equity by {difference}.",
            (LineItem.TOTAL_ASSETS, LineItem.TOTAL_LIABILITIES, LineItem.TOTAL_EQUITY),
        )
    ]


def check_gross_profit(
    facts: FinancialFactSet, relative_tolerance: Decimal = DEFAULT_RELATIVE_TOLERANCE
) -> list[Issue]:
    """Reported gross profit should equal revenue minus cost of revenue."""
    revenue = facts.get(LineItem.REVENUE)
    cost = facts.get(LineItem.COST_OF_REVENUE)
    gross_profit = facts.get(LineItem.GROSS_PROFIT)
    if revenue is None or cost is None or gross_profit is None:
        return []
    difference = gross_profit - (revenue - cost)
    if not _exceeds_tolerance(difference, revenue, relative_tolerance):
        return []
    return [
        Issue(
            IssueCode.SUBTOTAL_MISMATCH,
            Severity.WARNING,
            f"Gross profit differs from revenue minus cost of revenue by {difference}.",
            (LineItem.GROSS_PROFIT, LineItem.REVENUE, LineItem.COST_OF_REVENUE),
        )
    ]


def validate_fact_set(facts: FinancialFactSet) -> tuple[Issue, ...]:
    """Run every consistency check, in a fixed order."""
    return (
        *check_sign_conventions(facts),
        *check_balance_sheet_identity(facts),
        *check_gross_profit(facts),
    )
