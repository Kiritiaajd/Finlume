"""Turn a statement's raw rows into the normalised facts to store.

Each mapped row with an amount becomes one fact in base currency units,
scaled exactly by ``domain.financial_statements.normalize_amount``. Unmapped
rows and blank cells produce no fact: a missing figure is never zero. Signs
are kept as entered; the domain's validation reports unexpected ones.

The facts are returned unsaved. Validating a statement (MVP step 3) saves
them and changes its status in one transaction.
"""

from __future__ import annotations

from decimal import Decimal

from apps.financial_records.models import (
    FinancialFact,
    FinancialStatement,
    ReviewStatus,
    StatementLineItem,
)
from domain.financial_statements import LineItem, Scale, normalize_amount
from services.errors import ConflictError

#: ``numeric(30,6)`` holds magnitudes below 10^24 (FOUNDATION_AUDIT FA-15).
MAX_FACT_ABS = Decimal("1E+24")


def build_facts(
    statement: FinancialStatement, *, review_status: ReviewStatus
) -> list[FinancialFact]:
    """One query: the statement's mapped rows, in source order."""
    scale = Scale[statement.reported_scale.upper()]
    rows = StatementLineItem.objects.filter(statement=statement).exclude(line_item_code="")
    return [
        _fact(statement, row, row.reported_amount, scale, review_status)
        for row in rows.order_by("row_number")
        if row.reported_amount is not None  # a blank cell is unknown, not zero
    ]


def _fact(
    statement: FinancialStatement,
    row: StatementLineItem,
    amount: Decimal,
    scale: Scale,
    review_status: ReviewStatus,
) -> FinancialFact:
    item = LineItem(row.line_item_code)
    if item.statement_type.value != statement.statement_type:
        raise ConflictError(
            f"Row {row.row_number}: {item.value} belongs on the "
            f"{item.statement_type.value}, not the {statement.statement_type}."
        )
    value = normalize_amount(amount, scale)
    if abs(value) >= MAX_FACT_ABS:
        raise ConflictError(f"Row {row.row_number}: the amount is too large once scaled.")
    return FinancialFact(
        workspace_id=statement.workspace_id,
        entity_id=statement.entity_id,
        statement=statement,
        line_item=item.value,
        period_start=statement.period_start,
        period_end=statement.period_end,
        period_type=statement.period_type,
        currency=statement.currency,
        value=value,
        derived_from=row,
        review_status=review_status,
    )
