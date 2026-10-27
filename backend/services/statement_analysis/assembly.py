"""Assemble one analysis input from stored statements (rule A2, FOUNDATION_AUDIT FA-02).

For one entity and one reporting period, the input is the validated version
of each statement type: income statement, balance sheet and cash flow. A
balance sheet is stored against the period it closes, so it shares the
income statement's start, end and type. Drafts and superseded versions are
never used. A missing statement type is allowed; the engine reports its
ratios as ``missing_input``.

Only confirmed facts are used. All statements must share one currency,
because Finlume never converts currencies (decision D-03).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from apps.financial_records.models import (
    FinancialFact,
    FinancialStatement,
    ReportingEntity,
    ReviewStatus,
    StatementStatus,
)
from domain.financial_statements import Currency, FinancialFactSet, LineItem, ReportingPeriod
from services.errors import ConflictError


@dataclass(frozen=True)
class AnalysisInput:
    """What an analysis runs on, and the stored rows it came from.

    ``facts`` goes to the domain engine. ``statements`` and ``source_facts``
    are the exact versions and rows used, which an analysis run records.
    """

    facts: FinancialFactSet
    statements: tuple[FinancialStatement, ...]
    source_facts: tuple[FinancialFact, ...]


def assemble_analysis_input(*, entity: ReportingEntity, period: ReportingPeriod) -> AnalysisInput:
    """Two queries: the validated statements, then their confirmed facts.

    The caller has already resolved ``entity`` inside the caller's workspace.
    Raises ``ConflictError`` when nothing is validated for the period, or when
    the statements use different currencies.
    """
    statements = tuple(
        FinancialStatement.objects.filter(
            workspace_id=entity.workspace_id,
            entity=entity,
            period_start=period.start,
            period_end=period.end,
            period_type=period.period_type.value,
            status=StatementStatus.VALIDATED,
        ).order_by("statement_type")
    )
    if not statements:
        raise ConflictError("No validated statement exists for this entity and period.")
    currencies = sorted({statement.currency for statement in statements})
    if len(currencies) > 1:
        raise ConflictError(
            "The statements for this period use different currencies: "
            f"{', '.join(currencies)}. Finlume does not convert currencies."
        )

    source_facts = tuple(
        FinancialFact.objects.filter(
            workspace_id=entity.workspace_id,
            statement__in=statements,
            review_status=ReviewStatus.CONFIRMED,
        )
        .select_related("statement")
        .order_by("line_item")
    )
    values: dict[LineItem, Decimal] = {}
    for fact in source_facts:
        item = LineItem(fact.line_item)
        # The database does not tie a code to its statement type, so a stray
        # code could otherwise appear twice in one fact set.
        if item.statement_type.value != fact.statement.statement_type:
            raise ConflictError(
                f"The {fact.statement.statement_type} has a {item.value} figure, "
                f"which belongs on the {item.statement_type.value}."
            )
        values[item] = fact.value

    return AnalysisInput(
        facts=FinancialFactSet(currency=Currency(currencies[0]), period=period, values=values),
        statements=statements,
        source_facts=source_facts,
    )
