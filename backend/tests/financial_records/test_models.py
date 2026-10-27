"""Database constraints on entities, statements, line items and facts (DATA_MODEL §4.4 to 4.8)."""

from __future__ import annotations

import contextlib
from datetime import date
from decimal import Decimal

import pytest
from django.apps import apps
from django.db import DataError, IntegrityError, transaction

from apps.documents.models import SourceDocument
from apps.financial_records.models import (
    LINE_ITEMS,
    FinancialFact,
    FinancialStatement,
    StatementStatus,
)
from domain.financial_statements import LineItem, Scale, normalize_amount

pytestmark = pytest.mark.django_db

VALIDATED = StatementStatus.VALIDATED
DRAFT = StatementStatus.DRAFT
SUPERSEDED = StatementStatus.SUPERSEDED

FY2024 = {"period_start": date(2024, 1, 1), "period_end": date(2024, 12, 31)}


@contextlib.contextmanager
def rejected(constraint: str | None = None):
    """The database refuses the write, naming ``constraint`` (CHECKs name it on both engines)."""
    with pytest.raises(IntegrityError, match=constraint), transaction.atomic():
        yield


# --- Registration and the full chain ------------------------------------------------


def test_apps_are_registered():
    assert apps.get_app_config("documents").get_model("SourceDocument") is SourceDocument
    assert apps.get_app_config("financial_records").get_model("FinancialFact") is FinancialFact


def test_a_manual_statement_with_raw_rows_and_facts_can_be_stored(
    make_statement, make_line_item, make_fact
):
    statement = make_statement(reported_scale="lakhs")
    row = make_line_item(statement, "revenue", "12.5", raw_value="12.50")
    make_line_item(statement, "", None, label="Memo: rounding")  # blank cell, unmapped
    make_fact(row, value=normalize_amount(row.reported_amount, Scale.LAKHS))

    fact = FinancialFact.objects.get()
    assert fact.value == Decimal("1250000")
    assert fact.derived_from.raw_value == "12.50"
    assert fact.derived_from.reported_amount == Decimal("12.5")  # kept in the reported scale
    assert statement.line_items.count() == 2


def test_the_database_accepts_exactly_the_domain_taxonomy(make_statement, make_line_item):
    statement = make_statement()

    for row, item in enumerate(LineItem, start=1):
        make_line_item(statement, item.value, row_number=row)

    assert sorted(LINE_ITEMS) == sorted(item.value for item in LineItem)
    assert statement.line_items.count() == len(LineItem)


# --- ReportingEntity ----------------------------------------------------------------


def test_entity_names_are_unique_within_a_workspace_only(make_entity, make_workspace):
    first = make_entity(name="Example Co")
    make_entity(workspace=make_workspace(), name="Example Co")  # another workspace

    with rejected():
        make_entity(workspace=first.workspace, name="Example Co")


@pytest.mark.parametrize(
    ("fields", "constraint"),
    [
        ({"entity_type": "partnership"}, "entity_type_valid"),
        ({"default_currency": "usd"}, "currency_format"),
        ({"default_currency": "US"}, "currency_format"),
        ({"fiscal_year_end_month": 0}, "fiscal_month_valid"),
        ({"fiscal_year_end_month": 13}, "fiscal_month_valid"),
    ],
)
def test_invalid_entity_fields_are_rejected(make_entity, fields, constraint):
    with rejected(constraint):
        make_entity(**fields)


def test_entity_currency_and_fiscal_month_are_optional(make_entity):
    assert make_entity(default_currency="", fiscal_year_end_month=None).pk


# --- FinancialStatement: versions -------------------------------------------------


@pytest.mark.parametrize("status", [VALIDATED, DRAFT])
def test_a_second_validated_or_draft_version_of_the_same_statement_is_rejected(
    make_statement, restate, status
):
    first = make_statement(status=status)
    second = restate(first, status=SUPERSEDED)

    with rejected():
        restate(second, status=status)


def test_a_validated_version_and_its_draft_restatement_coexist(make_statement, restate):
    validated = make_statement(status=VALIDATED)

    draft = restate(validated)

    assert (draft.version, draft.supersedes) == (2, validated)


def test_superseded_versions_do_not_count_as_current(make_statement, restate):
    first = make_statement(status=SUPERSEDED)
    second = restate(first, status=SUPERSEDED)

    assert restate(second, status=VALIDATED).version == 3


def test_other_statement_types_periods_and_entities_have_their_own_current_version(
    make_statement, make_entity
):
    base = make_statement()

    make_statement(entity=base.entity, statement_type="balance_sheet")
    make_statement(entity=base.entity, **FY2024)
    make_statement(entity=make_entity(workspace=base.workspace))

    assert FinancialStatement.objects.filter(status=VALIDATED).count() == 4


def test_the_database_computes_the_previous_version(make_statement, restate):
    v1 = make_statement(status=SUPERSEDED)
    v2 = restate(v1)

    v1.refresh_from_db()
    v2.refresh_from_db()
    assert (v1.previous_version, v2.previous_version) == (0, 1)


def test_version_numbers_are_unique_per_statement(make_statement, restate):
    v1 = make_statement(status=SUPERSEDED)
    v3 = restate(restate(v1, status=SUPERSEDED), status=SUPERSEDED)

    with rejected():
        restate(v3, version=2)


@pytest.mark.parametrize(
    ("fields", "constraint"),
    [
        ({"version": 1, "supersedes": "earlier", "restatement_reason": "x"}, "version_supersedes"),
        ({"version": 2}, "version_supersedes"),
        ({"version": 0}, "version_"),
    ],
    ids=["version 1 restating", "version 2 restating nothing", "version 0"],
)
def test_version_and_supersedes_must_agree(make_statement, fields, constraint):
    earlier = make_statement(status=SUPERSEDED)
    if fields.get("supersedes") == "earlier":
        fields = {**fields, "supersedes": earlier}

    with rejected(constraint):
        make_statement(entity=earlier.entity, status=DRAFT, **FY2024, **fields)


@pytest.mark.parametrize("reason", ["", "   ", "\n\t "], ids=["empty", "spaces", "whitespace"])
def test_a_restatement_needs_a_reason(make_statement, restate, reason):
    first = make_statement(status=SUPERSEDED)

    with rejected("restatement_reason"):
        restate(first, restatement_reason=reason)


def test_a_reason_may_have_surrounding_whitespace(make_statement, restate):
    first = make_statement(status=SUPERSEDED)

    assert restate(first, restatement_reason="  Auditor adjustment\n").pk


def test_an_original_version_has_no_restatement_reason(make_statement):
    with rejected("restatement_reason"):
        make_statement(restatement_reason="Not a restatement")


# --- FinancialStatement: fields ---------------------------------------------------


@pytest.mark.parametrize(
    ("fields", "constraint"),
    [
        ({"currency": "usd"}, "currency_format"),
        ({"currency": "US"}, "currency_format"),
        ({"currency": "U$D"}, "currency_format"),
        ({"period_start": date(2025, 12, 31), "period_end": date(2025, 1, 1)}, "period_order"),
        ({"statement_type": "equity_statement"}, "statement_type_valid"),
        ({"period_type": "weekly"}, "period_type_valid"),
        ({"reported_scale": "hundreds"}, "reported_scale_valid"),
        ({"status": "approved"}, "status_valid"),
    ],
)
def test_invalid_statement_fields_are_rejected(make_statement, fields, constraint):
    with rejected(constraint):
        make_statement(**fields)


def test_a_four_letter_currency_does_not_fit(make_statement):
    # The column length on PostgreSQL (DataError); the format CHECK on SQLite.
    with pytest.raises((IntegrityError, DataError)), transaction.atomic():
        make_statement(currency="USDX")


def test_a_single_day_period_is_valid(make_statement):
    day = date(2025, 12, 31)

    assert make_statement(statement_type="balance_sheet", period_start=day, period_end=day).pk


# --- Line items and facts ---------------------------------------------------------


def test_a_code_is_mapped_at_most_once_per_statement(make_statement, make_line_item):
    statement = make_statement()
    make_line_item(statement, "revenue")
    make_line_item(statement, "")
    make_line_item(statement, "")  # several unmapped rows are fine
    make_line_item(make_statement(statement_type="balance_sheet"), "revenue")  # another statement

    with rejected():
        make_line_item(statement, "revenue")


def test_row_numbers_are_unique_and_positive_per_statement(make_statement, make_line_item):
    statement = make_statement()
    make_line_item(statement, "revenue", row_number=1)

    with rejected():
        make_line_item(statement, "cost_of_revenue", row_number=1)
    with rejected("row_positive"):
        make_line_item(statement, "cost_of_revenue", row_number=0)


def test_codes_outside_the_taxonomy_are_rejected(make_statement, make_line_item, make_fact):
    statement = make_statement()
    row = make_line_item(statement, "revenue")

    with rejected("code_valid"):
        make_line_item(statement, "ebitda")
    with rejected("line_item_valid"):
        make_fact(row, line_item="ebitda")


def test_a_statement_has_at_most_one_fact_per_line_item(make_statement, make_line_item, make_fact):
    statement = make_statement()
    make_fact(make_line_item(statement, "revenue"))
    other_row = make_line_item(statement, "cost_of_revenue")

    with rejected():
        make_fact(other_row, line_item="revenue")


def test_a_raw_row_normalises_into_at_most_one_fact(make_statement, make_line_item, make_fact):
    row = make_line_item(make_statement(), "revenue")
    make_fact(row)

    with rejected():
        make_fact(row)


def test_fact_review_status_is_checked(make_statement, make_line_item, make_fact):
    with rejected("review_status_valid"):
        make_fact(make_line_item(make_statement(), "revenue"), review_status="approved")
