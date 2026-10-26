from __future__ import annotations

from decimal import Decimal

from domain.financial_statements import LineItem
from domain.validation import (
    IssueCode,
    Severity,
    check_balance_sheet_identity,
    check_gross_profit,
    check_sign_conventions,
    validate_fact_set,
)


def test_consistent_statements_raise_no_issues(complete_facts):
    assert validate_fact_set(complete_facts) == ()


def test_balance_sheet_within_rounding_tolerance_passes(make_facts):
    # 0.05 % difference, typical of figures rounded to thousands.
    facts = make_facts(total_assets="1000000", total_liabilities="600000", total_equity="399500")

    assert check_balance_sheet_identity(facts) == []


def test_balance_sheet_imbalance_is_flagged(make_facts):
    facts = make_facts(total_assets="1000000", total_liabilities="600000", total_equity="300000")

    [issue] = check_balance_sheet_identity(facts)

    assert issue.code is IssueCode.BALANCE_SHEET_IMBALANCE
    assert issue.severity is Severity.WARNING
    assert "100000" in issue.message


def test_balance_sheet_check_skips_when_inputs_are_missing(make_facts):
    assert check_balance_sheet_identity(make_facts(total_assets="1000000")) == []


def test_gross_profit_mismatch_is_flagged(make_facts):
    facts = make_facts(revenue="1000", cost_of_revenue="600", gross_profit="500")

    [issue] = check_gross_profit(facts)

    assert issue.code is IssueCode.SUBTOTAL_MISMATCH
    assert issue.line_items == (LineItem.GROSS_PROFIT, LineItem.REVENUE, LineItem.COST_OF_REVENUE)


def test_sign_convention_violations_are_flagged(make_facts):
    facts = make_facts(revenue="-10", capital_expenditure="25", net_income="-5")

    issues = check_sign_conventions(facts)

    assert {issue.line_items[0] for issue in issues} == {
        LineItem.REVENUE,
        LineItem.CAPITAL_EXPENDITURE,
    }
    assert all(issue.code is IssueCode.UNEXPECTED_SIGN for issue in issues)


def test_losses_are_not_sign_violations(make_facts):
    facts = make_facts(net_income="-5", operating_income="-2", total_equity="-1")

    assert check_sign_conventions(facts) == []


def test_validation_never_mutates_facts(complete_facts):
    before = dict(complete_facts.values)

    validate_fact_set(complete_facts)

    assert dict(complete_facts.values) == before
    assert before[LineItem.REVENUE] == Decimal("1000000")
