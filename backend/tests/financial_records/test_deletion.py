"""Provenance is never broken, yet a whole workspace can be deleted (DATA_MODEL principle 4)."""

from __future__ import annotations

import pytest
from django.db import connection
from django.db.models import RestrictedError

from apps.documents.models import SourceDocument
from apps.financial_records.models import (
    FinancialFact,
    FinancialStatement,
    ReportingEntity,
    StatementLineItem,
    StatementStatus,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def chain(make_statement, restate, make_line_item, make_fact):
    """Version 1 (superseded) and version 2 (validated), each with a raw row and its fact."""
    v1 = make_statement(status=StatementStatus.SUPERSEDED)
    v1_row = make_line_item(v1, "revenue")
    v1_fact = make_fact(v1_row)
    v2 = restate(v1, status=StatementStatus.VALIDATED)
    make_fact(make_line_item(v2, "revenue"))
    return v1, v1_row, v1_fact, v2


def test_a_statement_with_facts_cannot_be_deleted(chain):
    _, _, _, v2 = chain

    with pytest.raises(RestrictedError):
        v2.delete()


def test_a_raw_row_with_a_fact_cannot_be_deleted(chain):
    _, v1_row, _, _ = chain

    with pytest.raises(RestrictedError):
        v1_row.delete()


def test_a_restated_version_cannot_be_deleted(chain):
    v1, _, v1_fact, _ = chain
    v1_fact.delete()  # facts are not what blocks it here

    with pytest.raises(RestrictedError):
        v1.delete()


def test_an_entity_with_statements_cannot_be_deleted(chain):
    v1, *_ = chain

    with pytest.raises(RestrictedError):
        v1.entity.delete()


def test_a_source_document_used_by_a_statement_cannot_be_deleted(chain):
    v1, *_ = chain

    with pytest.raises(RestrictedError):
        v1.source_document.delete()


def test_a_statement_without_facts_takes_its_raw_rows_with_it(make_statement, make_line_item):
    statement = make_statement(status=StatementStatus.DRAFT)
    make_line_item(statement, "revenue")

    statement.delete()

    assert not StatementLineItem.objects.exists()


def test_deleting_a_workspace_deletes_all_of_its_financial_records(chain, make_statement):
    v1, *_ = chain
    other = make_statement()  # another workspace, untouched

    v1.workspace.delete()

    assert list(ReportingEntity.objects.all()) == [other.entity]
    assert list(SourceDocument.objects.all()) == [other.source_document]
    assert list(FinancialStatement.objects.all()) == [other]
    assert not StatementLineItem.objects.exists()
    assert not FinancialFact.objects.exists()
    connection.check_constraints()  # every deferred foreign key, composite ones included
