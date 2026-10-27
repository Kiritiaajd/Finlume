from __future__ import annotations

from decimal import Decimal

import pytest

from domain.financial_statements import LineItem, StatementType
from domain.financial_statements.csv_import import (
    CsvFormatError,
    parse_amount,
    parse_statement_csv,
    propose_line_item,
)

# --- Amounts ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1234.56", "1234.56"),
        ("-1234.56", "-1234.56"),
        ("(1,234.56)", "-1234.56"),
        ("( 700.25 )", "-700.25"),
        ("1,234,567.89", "1234567.89"),
        ("1,23,456.78", "123456.78"),  # Indian grouping
        ("12,34,56,789", "123456789"),
        ("  42  ", "42"),
        ("0.000001", "0.000001"),
        ("12345678901234567890.123456", "12345678901234567890.123456"),  # beyond float precision
    ],
)
def test_amounts_are_read_exactly(text, expected):
    value = parse_amount(text)

    assert isinstance(value, Decimal)
    assert value == Decimal(expected)


def test_a_large_amount_keeps_every_digit():
    assert str(parse_amount("98,76,54,32,10,98,76,543.210987")) == "98765432109876543.210987"


@pytest.mark.parametrize("text", ["", "   "])
def test_an_empty_cell_is_unknown_not_zero(text):
    assert parse_amount(text) is None


@pytest.mark.parametrize(
    "text",
    [
        "1.234,56",  # European separators
        "₹1,234",
        "$12",
        "1e3",
        "+5",
        ".5",
        "1,,234",
        ",123",
        "123,",
        "1.2.3",
        "-(5)",
        "(-5)",
        "(5",
        "NaN",
        "Infinity",
        "twelve",
    ],
)
def test_other_formats_are_refused(text):
    with pytest.raises(ValueError, match="Not a number"):
        parse_amount(text)


# --- Files ------------------------------------------------------------------------------


def test_a_file_with_every_column():
    parsed = parse_statement_csv(
        "Label,Amount,Code\n"
        'Revenue from operations,"1,250.50",revenue\n'
        "Cost of materials,(700.25),COST_OF_REVENUE\n"
        "Other income,,\n",
        max_rows=10,
    )

    assert parsed.errors == {}
    assert [(r.line, r.label, r.code, r.amount, r.raw_amount) for r in parsed.rows] == [
        (2, "Revenue from operations", "revenue", Decimal("1250.50"), "1,250.50"),
        (3, "Cost of materials", "cost_of_revenue", Decimal("-700.25"), "(700.25)"),
        (4, "Other income", "", None, ""),
    ]


def test_columns_may_come_in_any_order_and_code_is_optional():
    parsed = parse_statement_csv("amount,label\n10,Revenue\n", max_rows=10)

    [row] = parsed.rows
    assert (row.label, row.code, row.amount) == ("Revenue", "", Decimal("10"))


def test_blank_lines_are_skipped_and_line_numbers_stay_true():
    parsed = parse_statement_csv("\nlabel,amount\n\nRevenue,1\n,\nNet income,2\n", max_rows=10)

    assert [(r.line, r.label) for r in parsed.rows] == [(4, "Revenue"), (6, "Net income")]


def test_quoted_cells_may_hold_commas_and_line_breaks():
    parsed = parse_statement_csv(
        'label,amount\n"Sales, net of\nreturns","1,000"\nTax,5\n', max_rows=10
    )

    assert [(r.line, r.label, r.amount) for r in parsed.rows] == [
        (3, "Sales, net of\nreturns", Decimal("1000")),
        (4, "Tax", Decimal("5")),
    ]


def test_row_problems_are_reported_by_line_and_column():
    parsed = parse_statement_csv(
        "label,amount,code\n"
        "Revenue,1.234,56,revenue\n"  # an unquoted comma splits the cell
        ",10,\n"
        "Sales,12abc,\n"
        "Profit,5,ebitda\n"
        "Fine,1,\n",
        max_rows=10,
    )

    assert [row.label for row in parsed.rows] == ["Fine"]
    assert parsed.errors[2] == {"row": ("Expected 3 columns, found 4.",)}
    assert parsed.errors[3] == {"label": ("A label is required.",)}
    assert "Not a number" in parsed.errors[4]["amount"][0]
    assert parsed.errors[5] == {"code": ("Unknown line-item code 'ebitda'.",)}


def test_overlong_cells_are_row_problems():
    parsed = parse_statement_csv(f"label,amount\n{'x' * 256},{'1' * 65}\n", max_rows=10)

    assert set(parsed.errors[2]) == {"label", "amount"}


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("", "empty"),
        ("\n \n", "empty"),
        ("label,amount\n", "no rows"),
        ("label\nRevenue\n", "no 'amount' column"),
        ("label,amount,notes\n", "Unknown column 'notes'"),
        ("label,amount,label\n", "'label' appears more than once"),
        ('label,amount\n"Revenue,1\n', "not valid CSV"),
    ],
)
def test_file_problems_stop_the_import(text, message):
    with pytest.raises(CsvFormatError, match=message):
        parse_statement_csv(text, max_rows=10)


def test_the_row_cap_counts_every_data_row():
    text = "label,amount\n" + "Row,1\n" * 3

    assert len(parse_statement_csv(text, max_rows=3).rows) == 3
    with pytest.raises(CsvFormatError, match="more than 2 rows"):
        parse_statement_csv(text, max_rows=2)


# --- Proposing codes ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("label", "statement_type", "expected"),
    [
        ("Revenue", StatementType.INCOME_STATEMENT, LineItem.REVENUE),
        ("  NET   income ", StatementType.INCOME_STATEMENT, LineItem.NET_INCOME),
        ("total_assets", StatementType.BALANCE_SHEET, LineItem.TOTAL_ASSETS),
        (
            "Cash and cash equivalents",
            StatementType.BALANCE_SHEET,
            LineItem.CASH_AND_CASH_EQUIVALENTS,
        ),
        ("Total assets", StatementType.INCOME_STATEMENT, None),  # wrong statement: not proposed
        ("Revenue from operations", StatementType.INCOME_STATEMENT, None),  # no fuzzy matching
        ("Sales", StatementType.INCOME_STATEMENT, None),
    ],
)
def test_codes_are_proposed_by_exact_name_only(label, statement_type, expected):
    assert propose_line_item(label, statement_type) is expected
