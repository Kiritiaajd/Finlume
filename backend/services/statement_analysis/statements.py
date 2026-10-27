"""Reporting entities and the lifecycle of statements entered by hand (MVP step 3).

Input shape and format (decimal strings, codes, scale limits) are checked by
the API serializers before these run. These functions enforce the state
rules: a statement exists once per entity, type and period; only a draft can
be edited; and a restatement keeps the type and period it restates.

Statuses change only in ``validate_statement``, which keeps them consistent
with the restatement chain: validating a draft makes it the validated version
and, for a restatement, supersedes exactly the version it restates.
``restate_statement`` only adds the next draft. Both lock the validated version
before the draft, in that order, so concurrent calls on one statement queue
instead of deadlocking.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.documents.models import SourceDocument, SourceDocumentKind
from apps.financial_records.models import (
    FinancialFact,
    FinancialStatement,
    ReportingEntity,
    ReviewStatus,
    StatementLineItem,
    StatementStatus,
)
from apps.workspaces.models import Workspace
from domain.financial_statements import (
    Currency,
    FinancialFactSet,
    LineItem,
    PeriodType,
    ReportingPeriod,
)
from domain.validation import Issue, validate_fact_set
from services.errors import ConflictError

from .normalisation import build_facts
from .rows import RowInput


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
    source: SourceDocument | None = None,
) -> FinancialStatement:
    """A new draft, version 1, with its raw rows.

    Its source is ``source`` (an uploaded file) or, by default, a new
    manual-entry document.
    """
    ensure_new_statement(
        entity=entity,
        statement_type=statement_type,
        period_start=period_start,
        period_end=period_end,
    )
    if source is None:
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


def ensure_new_statement(
    *, entity: ReportingEntity, statement_type: str, period_start: date, period_end: date
) -> None:
    """Refuse a second statement of one type for one entity and period."""
    if FinancialStatement.objects.filter(
        entity=entity,
        statement_type=statement_type,
        period_start=period_start,
        period_end=period_end,
    ).exists():
        raise _already_exists(statement_type)


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
    locked = _locked(statement.pk)
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


@dataclass(frozen=True)
class ValidationOutcome:
    """The validated statement and the consistency warnings on its figures.

    Warnings never block validation (FR-020 to FR-023): reported statements
    are often rounded, and the reviewer decides whether one matters.
    """

    statement: FinancialStatement
    issues: tuple[Issue, ...]


@transaction.atomic
def validate_statement(
    *, actor: User, workspace: Workspace, statement: FinancialStatement
) -> ValidationOutcome:
    """Draft → validated, with its facts saved as confirmed by ``actor``.

    For a restatement, the version it restates becomes ``superseded`` first:
    at most one version is validated, and that index cannot be deferred.
    """
    previous = None if statement.supersedes_id is None else _locked(statement.supersedes_id)
    draft = _locked(statement.pk)
    if draft.status != StatementStatus.DRAFT:
        raise ConflictError("Only a draft statement can be validated.")
    facts = build_facts(draft, review_status=ReviewStatus.CONFIRMED)
    if not facts:
        raise ConflictError("Map at least one row with an amount before validating.")
    reviewed_at = timezone.now()
    for fact in facts:
        fact.reviewed_by = actor
        fact.reviewed_at = reviewed_at

    if previous is not None:
        previous.status = StatementStatus.SUPERSEDED
        previous.save(update_fields=["status", "updated_at"])
    draft.status = StatementStatus.VALIDATED
    draft.save(update_fields=["status", "updated_at"])
    FinancialFact.objects.bulk_create(facts)

    issues = validate_fact_set(
        FinancialFactSet(
            currency=Currency(draft.currency),
            period=ReportingPeriod(
                draft.period_start, draft.period_end, PeriodType(draft.period_type)
            ),
            values={LineItem(fact.line_item): fact.value for fact in facts},
        )
    )
    AuditEvent.record(
        "statement.validated",
        actor=actor,
        workspace=workspace,
        target=draft,
        version=draft.version,
        superseded=str(previous.public_id) if previous else None,
        issues=len(issues),
    )
    return ValidationOutcome(statement=draft, issues=issues)


@transaction.atomic
def restate_statement(
    *,
    actor: User,
    workspace: Workspace,
    statement: FinancialStatement,
    reason: str,
    rows: Sequence[RowInput] | None = None,
) -> FinancialStatement:
    """The next version of a validated statement, as a draft.

    Without ``rows``, the draft starts from a copy of the validated version's
    rows. The validated version, its facts and the analyses that used them
    are left untouched until the draft is validated.
    """
    current = _locked(statement.pk)
    if current.status != StatementStatus.VALIDATED:
        raise ConflictError("Only the validated version of a statement can be restated.")
    if FinancialStatement.objects.filter(supersedes=current).exists():
        raise ConflictError(
            "This statement already has a restatement in progress. Edit or validate that draft."
        )
    if rows is None:
        rows = [_as_input(row) for row in current.line_items.order_by("row_number")]

    source = SourceDocument.objects.create(
        workspace=workspace, kind=SourceDocumentKind.MANUAL_ENTRY, created_by=actor
    )
    draft = FinancialStatement.objects.create(
        workspace=workspace,
        entity_id=current.entity_id,
        source_document=source,
        statement_type=current.statement_type,
        period_start=current.period_start,
        period_end=current.period_end,
        period_type=current.period_type,
        currency=current.currency,
        reported_scale=current.reported_scale,
        status=StatementStatus.DRAFT,
        version=current.version + 1,
        supersedes=current,
        restatement_reason=reason,
    )
    _replace_rows(draft, rows)
    AuditEvent.record(
        "statement.restated",
        actor=actor,
        workspace=workspace,
        target=draft,
        version=draft.version,
        restates=str(current.public_id),
    )
    return draft


def _locked(pk: int) -> FinancialStatement:
    return FinancialStatement.objects.select_for_update(of=("self",)).get(pk=pk)


def _as_input(row: StatementLineItem) -> RowInput:
    return {
        "label": row.label,
        "line_item_code": row.line_item_code,
        "amount": row.reported_amount,
        "raw_value": row.raw_value,
        "source_reference": row.source_reference,
    }


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
