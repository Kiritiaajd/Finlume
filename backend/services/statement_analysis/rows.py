"""Rules every raw row obeys, however it was entered (by hand or from a CSV).

- an amount has at most 6 decimal places and a magnitude below 10^24, both as
  entered and once scaled to base units, so it fits ``numeric(30,6)``
  (FOUNDATION_AUDIT FA-15);
- a line-item code belongs to the statement's type, and appears at most once.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import TypedDict

from domain.financial_statements import LineItem, Scale

MAX_ABS = Decimal("1E+24")  # numeric(30,6)
MAX_DECIMAL_PLACES = 6


class RowInput(TypedDict):
    """One raw row as entered. ``row_number`` comes from its position."""

    label: str
    line_item_code: str  # "" when unmapped
    amount: Decimal | None  # None for a blank cell
    raw_value: str
    source_reference: str


def amount_problem(value: Decimal) -> str | None:
    """Why ``value`` cannot be stored as entered, or ``None``."""
    exponent = value.normalize().as_tuple().exponent
    if isinstance(exponent, int) and -exponent > MAX_DECIMAL_PLACES:
        return f"Amounts have at most {MAX_DECIMAL_PLACES} decimal places."
    if abs(value) >= MAX_ABS:
        return "Amounts must be smaller than 10^24."
    return None


def row_problems(
    rows: Sequence[RowInput],
    *,
    statement_type: str,
    scale: Scale,
    names: Sequence[str] | None = None,
) -> dict[int, dict[str, list[str]]]:
    """Problems by row index, then field. ``names`` label rows in messages ("row 1")."""
    labels = names if names is not None else [f"row {index + 1}" for index in range(len(rows))]
    problems: dict[int, dict[str, list[str]]] = {}
    seen: dict[str, int] = {}
    for index, row in enumerate(rows):
        code, amount = row["line_item_code"], row["amount"]
        if code:
            home = LineItem(code).statement_type.value
            if home != statement_type:
                problems.setdefault(index, {})["line_item_code"] = [
                    f"{code} belongs on the {home}, not the {statement_type}."
                ]
            elif code in seen:
                problems.setdefault(index, {})["line_item_code"] = [
                    f"{code} is already on {labels[seen[code]]}."
                ]
            else:
                seen[code] = index
        if amount is not None:
            problem = amount_problem(amount)
            if problem is None and abs(amount.scaleb(scale.value)) >= MAX_ABS:
                problem = f"Too large once scaled from {scale.name.lower()} to units."
            if problem:
                problems.setdefault(index, {})["amount"] = [problem]
    return problems
