"""Reporting entities and draft statements entered by hand (MVP step 3a).

Input shape and format (decimal strings, codes, scale limits) are checked by
the API serializers before these run. These functions enforce the state
rules: a statement exists once per entity, type and period; only a draft can
be edited; and a restatement keeps the type and period it restates.
Validating and restating drafts arrive in step 3b.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import TypedDict

from django.db import IntegrityError, transaction

from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.documents.models import SourceDocument, SourceDocumentKind
from apps.financial_records.models import (
    FinancialStatement,
    ReportingEntity,
    StatementLineItem,
    StatementStatus,
)
from apps.workspaces.models import Workspace
from services.errors import ConflictError


class RowInput(TypedDict):
    """One raw row as entered. ``row_number`` comes from its position."""

    label: str
    line_item_code: str  # "" when unmapped
    amount: Decimal | None  # None for a blank cell
    raw_value: str
    source_reference: str


def create_entity(
    *,
    actor: User,
    workspace: Workspace,
    name: str,
    entity_type: str,
    default_currency: str = "",
    fiscal_year_end_month: int | None = None,
) -> ReportingEntity:
    try:
        with transaction.atomic():
            entity = ReportingEntity.objects.create(
                workspace=workspace,
                name=name,
                entity_type=entity_type,
                default_currency=default_currency,
                fiscal_year_end_month=fiscal_year_end_month,
            )
    except IntegrityError:
        raise ConflictError("This workspace already has an entity with this name.") from None
    AuditEvent.record("entity.created", actor=actor, workspace=workspace, target=entity)
    return entity


@transaction.atomic
def create_statement(
    *,
    actor: User,
    workspace: Workspace,
    entity: ReportingEntity,
    statement_type: str,
    period_start: date,
    period_end: date,
    period_type: str,
    currency: str,
    reported_scale: str,
    rows: Sequence[RowInput],
) -> FinancialStatement:
    """A new draft, version 1, with its raw rows and a manual-entry source."""
    if FinancialStatement.objects.filter(
        entity=entity,
        statement_type=statement_type,
        period_start=period_start,
        period_end=period_end,
    ).exists():
        raise _already_exists(statement_type)
    source = SourceDocument.objects.create(
        workspace=workspace, kind=SourceDocumentKind.MANUAL_ENTRY, created_by=actor
    )
    try:
        with transaction.atomic():
            statement = FinancialStatement.objects.create(
                workspace=workspace,
                entity=entity,
                source_document=source,
                statement_type=statement_type,
                period_start=period_start,
                period_end=period_end,
                period_type=period_type,
                currency=currency,
                reported_scale=reported_scale,
                status=StatementStatus.DRAFT,
            )
    except IntegrityError:  # created concurrently since the check above
        raise _already_exists(statement_type) from None
    _replace_rows(statement, rows)
    AuditEvent.record(
        "statement.created",
        actor=actor,
        workspace=workspace,
        target=statement,
        statement_type=statement_type,
    )
    return statement


#: Fields that identify a statement; a restatement may not change them.
_KEY_FIELDS = ("statement_type", "period_start", "period_end")
_EDITABLE_FIELDS = (*_KEY_FIELDS, "period_type", "currency", "reported_scale")


@transaction.atomic
def update_draft(
    *,
    actor: User,
    workspace: Workspace,
    statement: FinancialStatement,
    rows: Sequence[RowInput] | None = None,
    **changes: object,
) -> FinancialStatement:
    """Change a draft's header fields and, when ``rows`` is given, replace all its rows.

    The row is locked first, so an edit cannot interleave with validating the
    same draft (step 3b).
    """
    locked = FinancialStatement.objects.select_for_update(of=("self",)).get(pk=statement.pk)
    if locked.status != StatementStatus.DRAFT:
        raise ConflictError("Only a draft statement can be edited. Restate it instead.")
    unknown = set(changes) - set(_EDITABLE_FIELDS)
    if unknown:
        raise TypeError(f"Not editable: {', '.join(sorted(unknown))}")
    if locked.supersedes_id is not None and any(
        changes.get(field, getattr(locked, field)) != getattr(locked, field)
        for field in _KEY_FIELDS
    ):
        raise ConflictError(
            "A restatement keeps the statement type and period of the version it restates."
        )

    for field, value in changes.items():
        setattr(locked, field, value)
    try:
        with transaction.atomic():
            locked.save()
    except IntegrityError:
        raise _already_exists(locked.statement_type) from None
    if rows is not None:
        locked.line_items.all().delete()
        _replace_rows(locked, rows)
    AuditEvent.record(
        "statement.updated",
        actor=actor,
        workspace=workspace,
        target=locked,
        fields=sorted(changes),
        rows_replaced=rows is not None,
    )
    return locked


def _replace_rows(statement: FinancialStatement, rows: Sequence[RowInput]) -> None:
    StatementLineItem.objects.bulk_create(
        StatementLineItem(
            statement=statement,
            row_number=number,
            label=row["label"],
            line_item_code=row["line_item_code"],
            reported_amount=row["amount"],
            raw_value=row["raw_value"],
            source_reference=row["source_reference"],
        )
        for number, row in enumerate(rows, start=1)
    )


def _already_exists(statement_type: str) -> ConflictError:
    return ConflictError(
        f"This entity already has a {statement_type} for this period. "
        "Edit its draft, or restate the validated version."
    )
