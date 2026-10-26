"""Financial ratio definitions and their computation.

Each metric has a stable ``code`` and a plain-language ``methodology`` that is
stored with the result, so a saved analysis explains exactly how every number
was produced.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal, Overflow, localcontext
from enum import Enum
from types import MappingProxyType

from domain.financial_statements import FinancialFactSet, LineItem
from domain.validation import Issue, IssueCode, Severity

from .precision import CALCULATION_CONTEXT, MAX_RESULT_ABS, quantize_result


class MetricUnit(Enum):
    #: A pure ratio. Margins are ratios too: 0.25 means 25 %; converting to a
    #: percentage is a presentation concern.
    RATIO = "ratio"


@dataclass(frozen=True)
class RatioDefinition:
    code: str
    name: str
    numerator: LineItem
    denominator: LineItem
    methodology: str
    #: Flag results whose denominator is negative because the ratio stops
    #: being meaningful (e.g. return on negative equity).
    warn_on_negative_denominator: bool = False


@dataclass(frozen=True)
class MetricResult:
    code: str
    value: Decimal | None
    unit: MetricUnit
    methodology: str
    inputs: Mapping[LineItem, Decimal] = field(default_factory=dict)
    issues: tuple[Issue, ...] = ()

    @property
    def is_computable(self) -> bool:
        return self.value is not None


GROSS_MARGIN = RatioDefinition(
    "gross_margin",
    "Gross margin",
    LineItem.GROSS_PROFIT,
    LineItem.REVENUE,
    "Reported gross profit divided by revenue for the same period.",
)
OPERATING_MARGIN = RatioDefinition(
    "operating_margin",
    "Operating margin",
    LineItem.OPERATING_INCOME,
    LineItem.REVENUE,
    "Operating income divided by revenue for the same period.",
)
NET_MARGIN = RatioDefinition(
    "net_margin",
    "Net margin",
    LineItem.NET_INCOME,
    LineItem.REVENUE,
    "Net income divided by revenue for the same period.",
)
CURRENT_RATIO = RatioDefinition(
    "current_ratio",
    "Current ratio",
    LineItem.TOTAL_CURRENT_ASSETS,
    LineItem.TOTAL_CURRENT_LIABILITIES,
    "Total current assets divided by total current liabilities at period end.",
)
DEBT_TO_EQUITY = RatioDefinition(
    "debt_to_equity",
    "Debt to equity",
    LineItem.TOTAL_DEBT,
    LineItem.TOTAL_EQUITY,
    "Total debt divided by total equity at period end.",
    warn_on_negative_denominator=True,
)
RETURN_ON_EQUITY = RatioDefinition(
    "return_on_equity",
    "Return on equity",
    LineItem.NET_INCOME,
    LineItem.TOTAL_EQUITY,
    "Net income for the period divided by closing total equity. Uses closing "
    "rather than average equity because only one period is analysed.",
    warn_on_negative_denominator=True,
)
RETURN_ON_ASSETS = RatioDefinition(
    "return_on_assets",
    "Return on assets",
    LineItem.NET_INCOME,
    LineItem.TOTAL_ASSETS,
    "Net income for the period divided by closing total assets. Uses closing "
    "rather than average assets because only one period is analysed.",
)

#: Every ratio the engine computes, in report order.
RATIO_DEFINITIONS: tuple[RatioDefinition, ...] = (
    GROSS_MARGIN,
    OPERATING_MARGIN,
    NET_MARGIN,
    CURRENT_RATIO,
    DEBT_TO_EQUITY,
    RETURN_ON_EQUITY,
    RETURN_ON_ASSETS,
)


def compute_ratio(definition: RatioDefinition, facts: FinancialFactSet) -> MetricResult:
    """Compute one ratio, or explain why it cannot be computed.

    Missing inputs are never assumed to be zero, and a zero denominator yields
    no value rather than an error or infinity.
    """
    numerator = facts.get(definition.numerator)
    denominator = facts.get(definition.denominator)
    inputs = {
        item: value
        for item, value in (
            (definition.numerator, numerator),
            (definition.denominator, denominator),
        )
        if value is not None
    }

    def result(value: Decimal | None, *issues: Issue) -> MetricResult:
        return MetricResult(
            code=definition.code,
            value=value,
            unit=MetricUnit.RATIO,
            methodology=definition.methodology,
            inputs=MappingProxyType(inputs),
            issues=issues,
        )

    missing = tuple(
        item for item in (definition.numerator, definition.denominator) if item not in inputs
    )
    if numerator is None or denominator is None:
        names = " and ".join(item.value for item in missing)
        verb = "is" if len(missing) == 1 else "are"
        return result(
            None,
            Issue(
                IssueCode.MISSING_INPUT,
                Severity.WARNING,
                f"{definition.name} needs {names}, which {verb} not provided.",
                missing,
            ),
        )

    if denominator == 0:
        return result(
            None,
            Issue(
                IssueCode.ZERO_DENOMINATOR,
                Severity.WARNING,
                f"{definition.name} is undefined because {definition.denominator.value} is zero.",
                (definition.denominator,),
            ),
        )

    issues: list[Issue] = []
    if denominator < 0 and definition.warn_on_negative_denominator:
        issues.append(
            Issue(
                IssueCode.NEGATIVE_DENOMINATOR,
                Severity.WARNING,
                f"{definition.name} is not meaningful because "
                f"{definition.denominator.value} is negative.",
                (definition.denominator,),
            )
        )

    value: Decimal | None = None
    with localcontext(CALCULATION_CONTEXT):
        try:
            quotient = numerator / denominator
        except Overflow:
            quotient = None
        # Check before quantising (which would raise for very large values) and
        # after (rounding can carry a value up to the bound).
        if quotient is not None and abs(quotient) < MAX_RESULT_ABS:
            value = quantize_result(quotient)
        if value is None or abs(value) >= MAX_RESULT_ABS:
            return result(
                None,
                Issue(
                    IssueCode.RESULT_OUT_OF_RANGE,
                    Severity.WARNING,
                    f"{definition.name} cannot be reported because its magnitude is at "
                    f"least {MAX_RESULT_ABS:E}; check the scale of "
                    f"{definition.numerator.value} and {definition.denominator.value}.",
                    (definition.numerator, definition.denominator),
                ),
            )
    return result(value, *issues)
