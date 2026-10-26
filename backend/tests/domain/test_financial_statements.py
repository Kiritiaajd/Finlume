from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from domain.financial_statements import (
    Currency,
    FinancialFactSet,
    LineItem,
    PeriodType,
    ReportingPeriod,
    Scale,
    StatementType,
    normalize_amount,
)


@pytest.mark.parametrize(
    ("amount", "scale", "expected"),
    [
        ("12.5", Scale.UNITS, "12.5"),
        ("12.5", Scale.THOUSANDS, "12500"),
        ("3.25", Scale.LAKHS, "325000"),
        ("1.234567", Scale.MILLIONS, "1234567"),
        ("2", Scale.CRORES, "20000000"),
        ("-0.75", Scale.BILLIONS, "-750000000"),
    ],
)
def test_normalize_amount_is_exact(amount, scale, expected):
    assert normalize_amount(Decimal(amount), scale) == Decimal(expected)


def test_normalize_amount_preserves_very_large_values_exactly():
    amount = Decimal("123456789012345678.123456")

    assert normalize_amount(amount, Scale.BILLIONS) == Decimal("123456789012345678123456000")


@pytest.mark.parametrize("bad", [12.5, 12, "12.5"])
def test_monetary_inputs_must_be_decimal(bad):
    with pytest.raises(TypeError):
        normalize_amount(bad, Scale.UNITS)


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-Infinity"])
def test_monetary_inputs_must_be_finite(bad):
    with pytest.raises(ValueError, match="finite"):
        normalize_amount(Decimal(bad), Scale.UNITS)


@pytest.mark.parametrize("code", ["usd", "US", "USDT", "12A"])
def test_currency_rejects_malformed_codes(code):
    with pytest.raises(ValueError, match="three uppercase letters"):
        Currency(code)


def test_reporting_period_rejects_reversed_dates():
    with pytest.raises(ValueError, match="after its end"):
        ReportingPeriod(date(2025, 12, 31), date(2025, 1, 1), PeriodType.ANNUAL)


def test_balance_sheet_figures_are_as_of_period_end(fy2025):
    assert fy2025.as_of == date(2025, 12, 31)


def test_every_line_item_belongs_to_a_statement():
    for item in LineItem:
        assert isinstance(item.statement_type, StatementType)


def test_fact_set_is_immutable_and_treats_absent_items_as_missing(make_facts):
    facts = make_facts(revenue="100")

    assert facts.get(LineItem.REVENUE) == Decimal("100")
    assert facts.get(LineItem.NET_INCOME) is None
    with pytest.raises(TypeError):
        facts.values[LineItem.NET_INCOME] = Decimal("1")


def test_fact_set_rejects_float_values(fy2025):
    with pytest.raises(TypeError):
        FinancialFactSet(Currency("USD"), fy2025, {LineItem.REVENUE: 100.0})  # type: ignore[dict-item]
