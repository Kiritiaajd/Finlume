"""The analysis input fingerprint (calculation conventions §10, FOUNDATION_AUDIT FA-11)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from domain.calculations import fingerprint
from domain.financial_statements import (
    Currency,
    FinancialFactSet,
    LineItem,
    PeriodType,
    ReportingPeriod,
)

FY = ReportingPeriod(date(2025, 4, 1), date(2026, 3, 31), PeriodType.ANNUAL)

#: The documented example, hashed independently of ``fingerprint``.
GOLDEN = "beac7632d68475c8c89226e21559ad5639ff1b15a40deb5d4aca888498c1a9ce"


def facts(currency="INR", period=FY, **values):
    return FinancialFactSet(
        currency=Currency(currency),
        period=period,
        values={LineItem(code): Decimal(value) for code, value in values.items()},
    )


def test_the_documented_example_has_the_golden_fingerprint():
    assert fingerprint(facts(net_income="1250000", revenue="98000000")) == GOLDEN


def test_the_order_of_the_facts_does_not_matter():
    assert fingerprint(facts(revenue="98000000", net_income="1250000")) == GOLDEN


@pytest.mark.parametrize(
    ("first", "second"),
    [("1.0", "1.000000"), ("1250000", "1250000.000000"), ("0", "-0"), ("0.000000", "-0.0")],
)
def test_equal_values_written_differently_fingerprint_equally(first, second):
    assert fingerprint(facts(revenue=first)) == fingerprint(facts(revenue=second))


@pytest.mark.parametrize(
    "change",
    [
        {"values": {"revenue": "98000000.000001"}},
        {"values": {"revenue": "-98000000"}},
        {"values": {"total_assets": "98000000"}},  # same value, another line item
        {"values": {"revenue": "98000000", "net_income": "0"}},  # an extra fact
        {"currency": "USD"},
        {"period": ReportingPeriod(date(2025, 4, 1), date(2026, 3, 31), PeriodType.OTHER)},
        {"period": ReportingPeriod(date(2025, 4, 2), date(2026, 3, 31), PeriodType.ANNUAL)},
    ],
)
def test_any_difference_in_the_inputs_changes_the_fingerprint(change):
    base = facts(revenue="98000000")
    changed = facts(
        currency=change.get("currency", "INR"),
        period=change.get("period", FY),
        **change.get("values", {"revenue": "98000000"}),
    )

    assert fingerprint(changed) != fingerprint(base)


def test_more_than_six_decimal_places_is_refused_not_rounded():
    with pytest.raises(ValueError, match="revenue has more than 6 decimal places"):
        fingerprint(facts(revenue="1.0000001"))


def test_an_empty_fact_set_has_a_fingerprint():
    fingerprint_value = fingerprint(facts())

    assert len(fingerprint_value) == 64
    assert fingerprint_value == fingerprint_value.lower()


def test_the_fingerprint_does_not_depend_on_the_ambient_decimal_context():
    import decimal

    with decimal.localcontext(decimal.Context(prec=3, traps=[decimal.Inexact])):
        assert fingerprint(facts(net_income="1250000", revenue="98000000")) == GOLDEN
