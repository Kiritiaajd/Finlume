"""Raw rows to normalised facts: exact scaling, no invented zeros, provenance kept."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.db import connection

from apps.financial_records.models import FinancialFact, ReviewStatus
from services.errors import ConflictError
from services.statement_analysis import build_facts

pytestmark = pytest.mark.django_db

CONFIRMED = ReviewStatus.CONFIRMED


@pytest.mark.parametrize(
    ("scale", "amount", "value"),
    [
        ("units", "1234.56", "1234.56"),
        ("thousands", "1200.5", "1200500"),
        ("lakhs", "12.5", "1250000"),
        ("millions", "0.000001", "1"),
        ("crores", "-3.25", "-32500000"),  # signs are kept, never flipped
        ("billions", "2", "2000000000"),
    ],
)
def test_amounts_are_scaled_exactly_into_base_units(
    make_statement, make_line_item, scale, amount, value
):
    statement = make_statement(reported_scale=scale)
    make_line_item(statement, "net_income", amount)

    [fact] = build_facts(statement, review_status=CONFIRMED)

    assert fact.value == Decimal(value)


def test_each_fact_copies_its_statement_and_points_to_its_row(make_statement, make_line_item):
    statement = make_statement(currency="INR", period_type="annual")
    row = make_line_item(statement, "revenue", "10")

    [fact] = build_facts(statement, review_status=ReviewStatus.UNREVIEWED)

    assert fact.pk is None  # returned unsaved
    assert (fact.workspace_id, fact.entity_id, fact.statement) == (
        statement.workspace_id,
        statement.entity_id,
        statement,
    )
    assert (fact.period_start, fact.period_end, fact.period_type, fact.currency) == (
        statement.period_start,
        statement.period_end,
        "annual",
        "INR",
    )
    assert (fact.line_item, fact.derived_from, fact.review_status) == (
        "revenue",
        row,
        ReviewStatus.UNREVIEWED,
    )


def test_unmapped_rows_and_blank_cells_produce_no_fact(make_statement, make_line_item):
    statement = make_statement()
    make_line_item(statement, "revenue", "10")
    make_line_item(statement, "", "5", label="Memo line")  # unmapped
    make_line_item(statement, "cost_of_revenue", None)  # blank cell: unknown, not zero

    facts = build_facts(statement, review_status=CONFIRMED)

    assert [fact.line_item for fact in facts] == ["revenue"]


def test_facts_follow_the_source_row_order(make_statement, make_line_item):
    statement = make_statement()
    make_line_item(statement, "net_income", "1", row_number=3)
    make_line_item(statement, "revenue", "1", row_number=1)
    make_line_item(statement, "gross_profit", "1", row_number=2)

    facts = build_facts(statement, review_status=CONFIRMED)

    assert [fact.line_item for fact in facts] == ["revenue", "gross_profit", "net_income"]


def test_built_facts_save_and_satisfy_every_constraint(make_statement, make_line_item):
    statement = make_statement(reported_scale="lakhs")
    for code in ("revenue", "cost_of_revenue", "net_income"):
        make_line_item(statement, code, "12.345678")

    FinancialFact.objects.bulk_create(build_facts(statement, review_status=CONFIRMED))

    assert statement.facts.count() == 3
    assert statement.facts.get(line_item="revenue").value == Decimal("1234567.8")
    connection.check_constraints()  # the composite keys, on PostgreSQL


def test_building_facts_is_one_query(make_statement, make_line_item, django_assert_num_queries):
    statement = make_statement()
    for code in ("revenue", "cost_of_revenue", "net_income"):
        make_line_item(statement, code, "1")

    with django_assert_num_queries(1):
        build_facts(statement, review_status=CONFIRMED)


def test_a_code_from_another_statement_type_is_refused(make_statement, make_line_item):
    statement = make_statement(statement_type="income_statement")
    make_line_item(statement, "total_assets", "1", row_number=7)

    with pytest.raises(ConflictError, match="Row 7: total_assets belongs on the balance_sheet"):
        build_facts(statement, review_status=CONFIRMED)


def test_an_amount_too_large_to_store_once_scaled_is_refused(make_statement, make_line_item):
    statement = make_statement(reported_scale="billions")
    make_line_item(statement, "revenue", "999999999999999", row_number=4)  # just under 10^15
    make_line_item(statement, "net_income", "1000000000000000", row_number=5)  # 10^15 → 10^24

    with pytest.raises(ConflictError, match="Row 5: the amount is too large"):
        build_facts(statement, review_status=CONFIRMED)
