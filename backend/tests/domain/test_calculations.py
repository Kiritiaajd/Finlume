from __future__ import annotations

from decimal import Decimal, localcontext

import pytest

from domain.calculations import (
    ENGINE_VERSION,
    RATIO_DEFINITIONS,
    MetricUnit,
    compute_ratio,
    run_statement_analysis,
)
from domain.calculations.metrics import (
    CURRENT_RATIO,
    DEBT_TO_EQUITY,
    GROSS_MARGIN,
    NET_MARGIN,
    RETURN_ON_EQUITY,
)
from domain.financial_statements import LineItem
from domain.validation import IssueCode


@pytest.mark.parametrize(
    ("definition", "expected"),
    [
        (GROSS_MARGIN, "0.400000"),
        (NET_MARGIN, "0.100000"),
        (CURRENT_RATIO, "2.000000"),
        (DEBT_TO_EQUITY, "0.600000"),
        (RETURN_ON_EQUITY, "0.200000"),
    ],
)
def test_ratios_match_hand_calculated_values(complete_facts, definition, expected):
    result = compute_ratio(definition, complete_facts)

    assert result.value == Decimal(expected)
    assert result.unit is MetricUnit.RATIO
    assert result.issues == ()


def test_results_round_half_even_to_six_places(make_facts):
    # 1 / 3 = 0.333333...; 2.0000005 / 1 sits exactly on a rounding midpoint.
    third = compute_ratio(
        CURRENT_RATIO, make_facts(total_current_assets="1", total_current_liabilities="3")
    )
    midpoint = compute_ratio(
        CURRENT_RATIO, make_facts(total_current_assets="2.0000005", total_current_liabilities="1")
    )

    assert third.value == Decimal("0.333333")
    assert midpoint.value == Decimal("2.000000")


def test_results_do_not_depend_on_the_callers_decimal_context(complete_facts):
    expected = compute_ratio(GROSS_MARGIN, complete_facts).value

    with localcontext() as ctx:
        ctx.prec = 3
        assert compute_ratio(GROSS_MARGIN, complete_facts).value == expected


def test_missing_input_is_reported_not_assumed_zero(make_facts):
    result = compute_ratio(GROSS_MARGIN, make_facts(revenue="1000"))

    assert result.value is None
    assert not result.is_computable
    [issue] = result.issues
    assert issue.code is IssueCode.MISSING_INPUT
    assert issue.line_items == (LineItem.GROSS_PROFIT,)
    assert result.inputs == {LineItem.REVENUE: Decimal("1000")}


def test_zero_denominator_yields_no_value(make_facts):
    result = compute_ratio(NET_MARGIN, make_facts(net_income="10", revenue="0"))

    assert result.value is None
    assert [issue.code for issue in result.issues] == [IssueCode.ZERO_DENOMINATOR]


def test_negative_equity_is_computed_but_flagged(make_facts):
    result = compute_ratio(RETURN_ON_EQUITY, make_facts(net_income="10", total_equity="-50"))

    assert result.value == Decimal("-0.200000")
    assert [issue.code for issue in result.issues] == [IssueCode.NEGATIVE_DENOMINATOR]


@pytest.mark.parametrize(
    ("assets", "liabilities"),
    [
        # Both inputs fit numeric(30,6), yet the quotient needs > 34 digits at 6 dp.
        ("999999999999999999999999.999999", "0.000001"),
        # Fits the context but not the persisted numeric(24,6) result column.
        ("1E+20", "1"),
        ("-1E+18", "1"),
        # Below the bound, but rounds up to it at six decimal places.
        ("999999999999999999.9999995", "1"),
        # Exponent overflow of the decimal context itself.
        ("1E+999999", "1E-999999"),
    ],
)
def test_out_of_range_results_are_reported_not_raised(make_facts, assets, liabilities):
    result = compute_ratio(
        CURRENT_RATIO,
        make_facts(total_current_assets=assets, total_current_liabilities=liabilities),
    )

    assert result.value is None
    assert [issue.code for issue in result.issues] == [IssueCode.RESULT_OUT_OF_RANGE]


def test_largest_storable_result_is_kept(make_facts):
    result = compute_ratio(
        CURRENT_RATIO,
        make_facts(total_current_assets="999999999999999999.999999", total_current_liabilities="1"),
    )

    assert result.value == Decimal("999999999999999999.999999")


def test_missing_input_message_names_every_missing_item(make_facts):
    result = compute_ratio(GROSS_MARGIN, make_facts())

    [issue] = result.issues
    assert issue.message == ("Gross margin needs gross_profit and revenue, which are not provided.")


def test_metric_codes_are_unique():
    codes = [definition.code for definition in RATIO_DEFINITIONS]

    assert len(codes) == len(set(codes))


def test_analysis_is_deterministic_and_versioned(complete_facts):
    first = run_statement_analysis(complete_facts)
    second = run_statement_analysis(complete_facts)

    assert first == second
    assert first.engine_version == ENGINE_VERSION
    assert [metric.code for metric in first.metrics] == [d.code for d in RATIO_DEFINITIONS]
    assert first.validation_issues == ()


def test_analysis_reports_validation_issues_alongside_metrics(make_facts):
    outcome = run_statement_analysis(
        make_facts(revenue="1000", cost_of_revenue="600", gross_profit="500")
    )

    assert [issue.code for issue in outcome.validation_issues] == [IssueCode.SUBTOTAL_MISMATCH]
    gross_margin = next(metric for metric in outcome.metrics if metric.code == "gross_margin")
    assert gross_margin.value == Decimal("0.500000")
