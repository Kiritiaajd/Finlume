from __future__ import annotations

from dataclasses import dataclass

from domain.financial_statements import Currency, FinancialFactSet, ReportingPeriod
from domain.validation import Issue, validate_fact_set

from .metrics import RATIO_DEFINITIONS, MetricResult, compute_ratio
from .version import ENGINE_VERSION


@dataclass(frozen=True)
class AnalysisOutcome:
    """Everything needed to persist and reproduce one analysis run."""

    engine_version: str
    currency: Currency
    period: ReportingPeriod
    validation_issues: tuple[Issue, ...]
    metrics: tuple[MetricResult, ...]


def run_statement_analysis(facts: FinancialFactSet) -> AnalysisOutcome:
    """Validate a fact set and compute every ratio for it.

    Validation issues are reported alongside the metrics instead of blocking
    them: reported statements often contain rounding differences, and the
    reviewer decides whether a warning matters.
    """
    return AnalysisOutcome(
        engine_version=ENGINE_VERSION,
        currency=facts.currency,
        period=facts.period,
        validation_issues=validate_fact_set(facts),
        metrics=tuple(compute_ratio(definition, facts) for definition in RATIO_DEFINITIONS),
    )
