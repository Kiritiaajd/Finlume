"""Currency and reporting scale, the two units every monetary figure carries."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Context, Decimal, Inexact, InvalidOperation, Overflow
from enum import Enum

_CURRENCY_CODE = re.compile(r"[A-Z]{3}")

# Scaling must be exact regardless of the caller's ambient decimal context:
# any rounding raises instead of silently changing a reported figure.
_EXACT = Context(prec=100, traps=[Inexact, InvalidOperation, Overflow])


def ensure_finite_decimal(value: object, name: str = "value") -> Decimal:
    """Return ``value`` if it is a finite Decimal; reject floats, NaN and infinities."""
    if not isinstance(value, Decimal):
        raise TypeError(f"{name} must be a Decimal, got {type(value).__name__}.")
    if not value.is_finite():
        raise ValueError(f"{name} must be finite, got {value}.")
    return value


@dataclass(frozen=True)
class Currency:
    """An ISO 4217 alphabetic currency code such as ``USD`` or ``INR``.

    Only the code's shape is validated here; whether a code is one Finlume
    supports is decided at the input boundary.
    """

    code: str

    def __post_init__(self) -> None:
        if not _CURRENCY_CODE.fullmatch(self.code):
            raise ValueError(f"Currency code must be three uppercase letters, got {self.code!r}.")

    def __str__(self) -> str:
        return self.code


class Scale(Enum):
    """The multiplier a source document reports its figures in.

    The value is the power of ten, so normalising is exact (``Decimal.scaleb``).
    """

    UNITS = 0
    THOUSANDS = 3
    LAKHS = 5
    MILLIONS = 6
    CRORES = 7
    BILLIONS = 9


def normalize_amount(amount: Decimal, scale: Scale) -> Decimal:
    """Convert a figure reported in ``scale`` to base currency units, exactly."""
    return ensure_finite_decimal(amount, "amount").scaleb(scale.value, context=_EXACT)
