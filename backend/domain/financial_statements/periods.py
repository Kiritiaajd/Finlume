from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum


class PeriodType(Enum):
    ANNUAL = "annual"
    HALF_YEAR = "half_year"
    QUARTER = "quarter"
    MONTH = "month"
    OTHER = "other"


@dataclass(frozen=True)
class ReportingPeriod:
    """The period a set of figures covers.

    Flow statements (income, cash flow) cover ``start``..``end`` inclusive.
    Balance sheet figures are a position at ``end`` (see ``as_of``).
    """

    start: date
    end: date
    period_type: PeriodType

    def __post_init__(self) -> None:
        if self.start > self.end:
            raise ValueError(f"Period start {self.start} is after its end {self.end}.")

    @property
    def as_of(self) -> date:
        return self.end
