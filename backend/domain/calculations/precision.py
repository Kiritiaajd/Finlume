"""Arithmetic precision and rounding policy for every calculation."""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Context, Decimal, DivisionByZero, InvalidOperation, Overflow

#: Calculations run in an explicit context rather than the thread's ambient
#: one, so results cannot depend on whatever context the caller configured.
CALCULATION_CONTEXT = Context(
    prec=34,
    rounding=ROUND_HALF_EVEN,
    traps=[InvalidOperation, DivisionByZero, Overflow],
)

#: Stored results keep six decimal places (e.g. a ratio of 0.123457).
#: Rounding for display happens in the presentation layer, never here.
RESULT_DECIMAL_PLACES = 6
_RESULT_QUANTUM = Decimal(1).scaleb(-RESULT_DECIMAL_PLACES)

#: Results must satisfy ``abs(value) < MAX_RESULT_ABS`` so that, at six decimal
#: places, they fit the persisted ``numeric(24,6)`` column and the calculation
#: context. Larger quotients (e.g. a tiny denominator) are reported, not raised.
MAX_RESULT_ABS = Decimal("1E+18")


def quantize_result(value: Decimal) -> Decimal:
    return value.quantize(_RESULT_QUANTUM, context=CALCULATION_CONTEXT)
