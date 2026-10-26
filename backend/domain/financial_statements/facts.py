from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType

from .line_items import LineItem
from .periods import ReportingPeriod
from .units import Currency, ensure_finite_decimal


@dataclass(frozen=True)
class FinancialFactSet:
    """Verified, normalised figures for one entity, one period and one currency.

    Every value is in base currency units (already multiplied out of its
    reporting scale) and follows the sign convention in ``line_items``. A
    missing line item is simply absent: it is never treated as zero.
    """

    currency: Currency
    period: ReportingPeriod
    values: Mapping[LineItem, Decimal]

    def __post_init__(self) -> None:
        checked: dict[LineItem, Decimal] = {}
        for item, value in self.values.items():
            if not isinstance(item, LineItem):
                raise TypeError(f"Fact keys must be LineItem members, got {item!r}.")
            checked[item] = ensure_finite_decimal(value, item.value)
        object.__setattr__(self, "values", MappingProxyType(checked))

    def get(self, item: LineItem) -> Decimal | None:
        return self.values.get(item)
