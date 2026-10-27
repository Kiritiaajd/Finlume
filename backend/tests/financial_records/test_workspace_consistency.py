"""Related rows cannot be connected across workspaces, and facts match their statement.

Enforced by the composite foreign keys of migration 0002, which exist on
PostgreSQL only. They are deferred, like Django's own foreign keys, so each
test forces the check with ``connection.check_constraints()``.
"""

from __future__ import annotations

import contextlib
from datetime import date

import pytest
from django.db import IntegrityError, connection, transaction

from apps.financial_records.models import FinancialStatement, StatementStatus

pytestmark = [pytest.mark.postgres, pytest.mark.django_db]


@contextlib.contextmanager
def _checked_on_exit():
    yield
    connection.check_constraints()


@contextlib.contextmanager
def violates(constraint: str):
    """The writes inside fail ``constraint`` once the deferred checks run."""
    with (
        pytest.raises(IntegrityError, match=constraint),
        transaction.atomic(),
        _checked_on_exit(),
    ):
        yield


def test_a_consistent_chain_passes_every_check(make_statement, restate, make_line_item, make_fact):
    v1 = make_statement(status=StatementStatus.SUPERSEDED)
    make_fact(make_line_item(restate(v1), "revenue"))

    connection.check_constraints()


# --- Statements ----------------------------------------------------------------------


def test_a_statement_cannot_use_an_entity_from_another_workspace(
    make_entity, make_source, make_statement, make_workspace
):
    entity = make_entity()
    elsewhere = make_workspace()

    with violates("entity_same_workspace"):
        make_statement(entity=entity, workspace=elsewhere, source_document=make_source(elsewhere))


def test_a_statement_cannot_use_a_source_document_from_another_workspace(
    make_source, make_statement, make_workspace
):
    with violates("source_same_workspace"):
        make_statement(source_document=make_source(make_workspace()))


@pytest.mark.parametrize("change", ["entity", "statement type", "period", "workspace"])
def test_a_restatement_stays_within_the_same_statement(
    make_statement, restate, make_entity, make_source, make_workspace, change
):
    original = make_statement(status=StatementStatus.SUPERSEDED)
    if change == "entity":
        fields = {"entity": make_entity(workspace=original.workspace)}
    elif change == "statement type":
        fields = {"statement_type": "balance_sheet"}
    elif change == "period":
        fields = {"period_start": date(2024, 1, 1), "period_end": date(2024, 12, 31)}
    else:
        elsewhere = make_workspace()
        entity = make_entity(workspace=elsewhere)
        fields = {
            "entity": entity,
            "workspace": elsewhere,
            "source_document": make_source(elsewhere),
        }

    with violates("supersedes_same_key"):
        restate(original, **fields)


def test_a_chain_of_restatements_passes(make_statement, restate):
    v1 = make_statement(status=StatementStatus.SUPERSEDED)
    v2 = restate(v1, status=StatementStatus.SUPERSEDED)
    restate(v2, status=StatementStatus.VALIDATED)

    connection.check_constraints()


def test_a_version_cannot_restate_itself(make_statement, restate):
    v2 = restate(make_statement(status=StatementStatus.SUPERSEDED))

    with violates("supersedes_same_key"):
        FinancialStatement.objects.filter(pk=v2.pk).update(supersedes=v2)


def test_a_restatement_cannot_skip_a_version(make_statement, restate):
    v1 = make_statement(status=StatementStatus.SUPERSEDED)

    with violates("supersedes_same_key"):
        restate(v1, version=3)


def test_a_version_cannot_restate_a_later_version(make_statement, restate):
    v1 = make_statement(status=StatementStatus.SUPERSEDED)
    v2 = restate(v1, status=StatementStatus.SUPERSEDED)
    v3 = restate(v2)

    with violates("supersedes_same_key"):
        # Re-point the chain so version 2 restates version 3, and 3 restates 1.
        FinancialStatement.objects.filter(pk=v2.pk).update(supersedes=v3)
        FinancialStatement.objects.filter(pk=v3.pk).update(supersedes=v1)


# --- Facts ----------------------------------------------------------------------------


@pytest.fixture
def row(make_statement, make_line_item):
    return make_line_item(make_statement(), "revenue")


@pytest.mark.parametrize(
    "field",
    ["workspace", "entity", "period_start", "period_end", "period_type", "currency"],
)
def test_a_fact_must_match_its_statement(row, make_entity, make_workspace, make_fact, field):
    different = {
        "workspace": lambda: make_workspace(),
        "entity": lambda: make_entity(workspace=row.statement.workspace),
        "period_start": lambda: date(2025, 2, 1),
        "period_end": lambda: date(2025, 6, 30),
        "period_type": lambda: "other",
        "currency": lambda: "EUR",
    }[field]()

    with violates("matches_statement"):
        make_fact(row, **{field: different})


def test_a_fact_cannot_derive_from_another_statements_row(
    row, make_statement, make_line_item, make_fact
):
    # Same entity, period and currency, so only the row's statement differs.
    sibling = make_statement(entity=row.statement.entity, statement_type="balance_sheet")
    elsewhere = make_line_item(sibling, "revenue")

    with violates("derived_from_same_statement"):
        make_fact(elsewhere, statement=row.statement)


def test_a_fact_has_the_code_of_its_raw_row(row, make_fact):
    with violates("derived_from_same_statement"):
        make_fact(row, line_item="cost_of_revenue")


def test_an_unmapped_row_cannot_become_a_fact(row, make_line_item, make_fact):
    unmapped = make_line_item(row.statement, "")

    with violates("derived_from_same_statement"):
        make_fact(unmapped, line_item="cost_of_revenue")


def test_a_statement_with_facts_cannot_change_the_fields_its_facts_copy(row, make_fact):
    make_fact(row)
    statement = row.statement

    with violates("matches_statement"):
        statement.currency = "EUR"
        statement.save(update_fields=["currency"])
