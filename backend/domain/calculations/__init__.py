"""Deterministic, versioned financial calculations."""

from .analysis import AnalysisOutcome, run_statement_analysis
from .metrics import RATIO_DEFINITIONS, MetricResult, MetricUnit, RatioDefinition, compute_ratio
from .version import ENGINE_VERSION

__all__ = [
    "ENGINE_VERSION",
    "RATIO_DEFINITIONS",
    "AnalysisOutcome",
    "MetricResult",
    "MetricUnit",
    "RatioDefinition",
    "compute_ratio",
    "run_statement_analysis",
]
