"""Consistency checks on normalised financial facts.

Checks never modify data. They report ``Issue`` objects so a reviewer can
decide whether the figures, or the source they came from, need correcting.
"""

from .checks import (
    DEFAULT_RELATIVE_TOLERANCE,
    check_balance_sheet_identity,
    check_gross_profit,
    check_sign_conventions,
    validate_fact_set,
)
from .issues import Issue, IssueCode, Severity

__all__ = [
    "DEFAULT_RELATIVE_TOLERANCE",
    "Issue",
    "IssueCode",
    "Severity",
    "check_balance_sheet_identity",
    "check_gross_profit",
    "check_sign_conventions",
    "validate_fact_set",
]
