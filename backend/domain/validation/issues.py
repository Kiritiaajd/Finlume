from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from domain.financial_statements import LineItem


class Severity(Enum):
    INFO = "info"
    WARNING = "warning"  # result is usable but should be reviewed
    ERROR = "error"  # input cannot be analysed until corrected


class IssueCode(str, Enum):
    """Stable, machine-readable issue codes (persisted and exposed via the API)."""

    MISSING_INPUT = "missing_input"
    ZERO_DENOMINATOR = "zero_denominator"
    NEGATIVE_DENOMINATOR = "negative_denominator"
    UNEXPECTED_SIGN = "unexpected_sign"
    BALANCE_SHEET_IMBALANCE = "balance_sheet_imbalance"
    SUBTOTAL_MISMATCH = "subtotal_mismatch"
    RESULT_OUT_OF_RANGE = "result_out_of_range"


@dataclass(frozen=True)
class Issue:
    code: IssueCode
    severity: Severity
    message: str
    line_items: tuple[LineItem, ...] = ()
