"""Builders for financial records (fictional data only).

Plain ORM writes, until the statement use cases of MVP step 3 exist. Every
builder keeps related rows in one workspace unless a test overrides a field.
"""

from __future__ import annotations

import itertools
from datetime import date
from decimal import Decimal

import pytest

from apps.documents.models import SourceDocument, SourceDocumentKind
from apps.financial_records.models import (
    EntityType,
    FinancialFact,
    FinancialStatement,
    ReportingEntity,
    ReviewStatus,
    StatementLineItem,
    StatementStatus,
)
from apps.workspaces.models import Workspace


@pytest.fixture
def make_entity(make_workspace):
    numbers = itertools.count(1)

    def build(workspace: Workspace | None = None, **fields) -> ReportingEntity:
        fields.setdefault("name", f"Example Trading Co {next(numbers)}")
        fields.setdefault("entity_type", EntityType.BUSINESS)
        return ReportingEntity.objects.create(workspace=workspace or make_workspace(), **fields)

    return build


@pytest.fixture
def make_source():
    def build(workspace: Workspace) -> SourceDocument:
        return SourceDocument.objects.create(
            workspace=workspace, kind=SourceDocumentKind.MANUAL_ENTRY
        )

    return build


@pytest.fixture
def make_statement(make_entity, make_source):
    """An FY2025 income statement in USD, version 1, by default validated."""

    def build(entity: ReportingEntity | None = None, **fields) -> FinancialStatement:
        entity = entity or make_entity()
        fields.setdefault("workspace", entity.workspace)
        if "source_document" not in fields:
            fields["source_document"] = make_source(entity.workspace)
        fields.setdefault("statement_type", "income_statement")
        fields.setdefault("period_start", date(2025, 1, 1))
        fields.setdefault("period_end", date(2025, 12, 31))
        fields.setdefault("period_type", "annual")
        fields.setdefault("currency", "USD")
        fields.setdefault("reported_scale", "thousands")
        fields.setdefault("status", StatementStatus.VALIDATED)
        return FinancialStatement.objects.create(entity=entity, **fields)

    return build


@pytest.fixture
def restate(make_statement):
    """Version ``n + 1`` of ``statement``, as a draft."""

    def build(statement: FinancialStatement, **fields) -> FinancialStatement:
        values = {
            "entity": statement.entity,
            "source_document": statement.source_document,
            "statement_type": statement.statement_type,
            "period_start": statement.period_start,
            "period_end": statement.period_end,
            "period_type": statement.period_type,
            "currency": statement.currency,
            "reported_scale": statement.reported_scale,
            "version": statement.version + 1,
            "supersedes": statement,
            "status": StatementStatus.DRAFT,
            "restatement_reason": "Auditor adjustment",
        }
        return make_statement(**{**values, **fields})

    return build


@pytest.fixture
def make_line_item():
    rows = itertools.count(1)

    def build(
        statement: FinancialStatement,
        code: str = "revenue",
        amount: str | None = "1200.5",
        **fields,
    ) -> StatementLineItem:
        return StatementLineItem.objects.create(
            statement=statement,
            row_number=fields.pop("row_number", next(rows)),
            label=fields.pop("label", code.replace("_", " ").title() or "Unmapped"),
            line_item_code=code,
            reported_amount=None if amount is None else Decimal(amount),
            raw_value=fields.pop("raw_value", amount or ""),
            **fields,
        )

    return build


@pytest.fixture
def make_fact():
    """The fact normalised from ``row``, copying its statement's fields."""

    def build(row: StatementLineItem, **fields) -> FinancialFact:
        statement = row.statement
        values = {
            "workspace": statement.workspace,
            "entity": statement.entity,
            "statement": statement,
            "line_item": row.line_item_code,
            "period_start": statement.period_start,
            "period_end": statement.period_end,
            "period_type": statement.period_type,
            "currency": statement.currency,
            "value": Decimal("1200500"),
            "derived_from": row,
            "review_status": ReviewStatus.CONFIRMED,
        }
        return FinancialFact.objects.create(**{**values, **fields})

    return build
