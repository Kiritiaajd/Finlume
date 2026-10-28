"""Request and response shapes for analysis runs."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.analysis.models import (
    METRIC_CODES,
    UNITS,
    AnalysisIssue,
    AnalysisRun,
    AnalysisRunInputFact,
    MetricResult,
)
from apps.financial_records.api.serializers import IssueSerializer
from apps.financial_records.models import LINE_ITEMS, PERIOD_TYPES
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


# --- Responses (for the OpenAPI schema; built by the functions below) -----------------


class RunSummarySerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    entity_id = serializers.UUIDField()
    period_start = serializers.DateField()
    period_end = serializers.DateField()
    period_type = serializers.ChoiceField(choices=PERIOD_TYPES)
    currency = serializers.CharField()
    engine_version = serializers.CharField()
    input_fingerprint = serializers.CharField()
    uses_superseded_statement = serializers.BooleanField(
        help_text="True once a statement this run used was restated; the run keeps its figures."
    )
    created_at = serializers.DateTimeField()


class MetricSerializer(serializers.Serializer[Any]):
    code = serializers.ChoiceField(choices=METRIC_CODES)
    name = serializers.CharField()
    value = serializers.CharField(
        allow_null=True, help_text="Decimal string; null when not computable, never 0."
    )
    unit = serializers.ChoiceField(choices=UNITS)
    methodology = serializers.CharField()
    inputs = serializers.DictField(
        child=serializers.CharField(), help_text="Line-item code to decimal string, base units."
    )
    issues = IssueSerializer(many=True)


class RunInputSerializer(serializers.Serializer[Any]):
    """One figure the engine saw, traced to its row, statement version and document."""

    line_item = serializers.ChoiceField(choices=LINE_ITEMS)
    value = serializers.CharField()
    row_id = serializers.UUIDField()
    statement_id = serializers.UUIDField()
    statement_version = serializers.IntegerField()
    document_id = serializers.UUIDField()


class RunDetailSerializer(RunSummarySerializer):
    metrics = MetricSerializer(many=True)
    issues = IssueSerializer(many=True)
    inputs = RunInputSerializer(many=True)


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
