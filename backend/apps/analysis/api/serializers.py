"""Request and response shapes for analysis runs."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.analysis.models import AnalysisIssue, AnalysisRun, AnalysisRunInputFact, MetricResult
from apps.financial_records.models import PERIOD_TYPES
from domain.calculations import RATIO_DEFINITIONS

_NAMES = {definition.code: definition.name for definition in RATIO_DEFINITIONS}


class AnalysisRequestSerializer(serializers.Serializer[Any]):
    """The reporting period to analyse; every statement type of it is used."""

    period_start = serializers.DateField()
    period_end = serializers.DateField()
    period_type = serializers.ChoiceField(choices=PERIOD_TYPES)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if attrs["period_start"] > attrs["period_end"]:
            raise serializers.ValidationError({"period_end": ["The period ends before it starts."]})
        return attrs


def run_summary(run: AnalysisRun) -> dict[str, Any]:
    """Expects ``entity`` loaded and the ``uses_superseded_statement`` annotation."""
    return {
        "id": run.public_id,
        "entity_id": run.entity.public_id,
        "period_start": run.period_start,
        "period_end": run.period_end,
        "period_type": run.period_type,
        "currency": run.currency,
        "engine_version": run.engine_version,
        "input_fingerprint": run.input_fingerprint,
        # True once a statement this run used has been restated: the run is
        # still valid for the figures it used, and a new run would differ.
        "uses_superseded_statement": run.uses_superseded_statement,  # type: ignore[attr-defined]
        "created_at": run.created_at,
    }


def issue_data(issue: AnalysisIssue) -> dict[str, Any]:
    return {
        "code": issue.code,
        "severity": issue.severity,
        "message": issue.message,
        "line_items": issue.line_items,
    }


def run_detail(
    run: AnalysisRun,
    metrics: list[MetricResult],
    issues: list[AnalysisIssue],
    inputs: list[AnalysisRunInputFact],
) -> dict[str, Any]:
    """The whole run: metrics with their methodology and inputs, issues, and traced inputs."""
    by_metric: dict[str, list[dict[str, Any]]] = {}
    for issue in issues:
        by_metric.setdefault(issue.metric_code, []).append(issue_data(issue))
    return {
        **run_summary(run),
        "metrics": [
            {
                "code": metric.metric_code,
                "name": _NAMES.get(metric.metric_code, metric.metric_code),
                "value": None if metric.value is None else format(metric.value, "f"),
                "unit": metric.unit,
                "methodology": metric.methodology,
                "inputs": metric.inputs,
                "issues": by_metric.get(metric.metric_code, []),
            }
            for metric in metrics
        ],
        "issues": by_metric.get("", []),
        # Every figure the engine saw, traced to its row, statement version and document.
        "inputs": [
            {
                "line_item": link.fact.line_item,
                "value": format(link.fact.value, "f"),
                "row_id": link.fact.derived_from.public_id,
                "statement_id": link.fact.statement.public_id,
                "statement_version": link.fact.statement.version,
                "document_id": link.fact.statement.source_document.public_id,
            }
            for link in inputs
        ],
    }
