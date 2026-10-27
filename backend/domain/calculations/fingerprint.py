"""The input fingerprint stored with every analysis run (calculation conventions §10).

The fingerprint is the SHA-256 (lowercase hex) of a canonical JSON document:

    {"currency":"INR","facts":[["net_income","1250000.000000"],...],
     "period":{"end":"2026-03-31","start":"2025-04-01","type":"annual"}}

Facts are sorted by line-item code, and values are fixed-point strings with
exactly six decimal places. Keys are sorted, there is no insignificant
whitespace, and the text is ASCII. Equal inputs therefore always hash
equally, and with the same engine version they produce the same results. The
engine version is stored next to the fingerprint, not inside it.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Context, Decimal, Inexact

from domain.financial_statements import FinancialFactSet

#: Facts are persisted with six decimal places (``numeric(30,6)``).
FACT_DECIMAL_PLACES = 6
_QUANTUM = Decimal(1).scaleb(-FACT_DECIMAL_PLACES)
# Quantising must never round: a value with more places is refused instead.
_EXACT = Context(prec=60, traps=[Inexact])


def fingerprint(facts: FinancialFactSet) -> str:
    """The canonical SHA-256 of ``facts``. Raises ``ValueError`` for more than 6 decimal places."""
    document = {
        "currency": facts.currency.code,
        "period": {
            "start": facts.period.start.isoformat(),
            "end": facts.period.end.isoformat(),
            "type": facts.period.period_type.value,
        },
        "facts": [
            [item.value, _fixed(value, item.value)]
            for item, value in sorted(facts.values.items(), key=lambda pair: pair[0].value)
        ],
    }
    text = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def _fixed(value: Decimal, name: str) -> str:
    try:
        exact = value.quantize(_QUANTUM, context=_EXACT)
    except Inexact:
        raise ValueError(
            f"{name} has more than {FACT_DECIMAL_PLACES} decimal places; it is never rounded."
        ) from None
    if exact == 0:
        exact = abs(exact)  # -0 and 0 are the same input
    return format(exact, "f")
