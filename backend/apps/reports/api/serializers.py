"""Request and response shapes for reports."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from api.schema import AllFieldsOptional
from apps.analysis.api.serializers import RunSummarySerializer, issue_data, run_summary
from apps.analysis.models import METRIC_CODES, UNITS, AnalysisIssue, AnalysisRun, MetricResult
from apps.financial_records.api.serializers import IssueSerializer
from apps.reports.models import Report
from domain.calculations import RATIO_DEFINITIONS

_NAMES = {definition.code: definition.name for definition in RATIO_DEFINITIONS}


class ReportInputSerializer(serializers.Serializer[Any]):
    """Create a report."""

    title = serializers.CharField(max_length=200)
    notes = serializers.CharField(max_length=10_000, allow_blank=True, default="")
    run_ids = serializers.ListField(child=serializers.UUIDField(), default=list)


class ReportUpdateSerializer(AllFieldsOptional, ReportInputSerializer):
    """Change part of a report (PATCH); ``run_ids`` replaces the whole ordered list."""


# --- Responses (for the OpenAPI schema; built by the functions below) -----------------


class ReportSummarySerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    title = serializers.CharField()
    run_count = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class ReportMetricSerializer(serializers.Serializer[Any]):
    code = serializers.ChoiceField(choices=METRIC_CODES)
    name = serializers.CharField()
    value = serializers.CharField(allow_null=True)
    unit = serializers.ChoiceField(choices=UNITS)


class ReportIssueSerializer(IssueSerializer):
    metric_code = serializers.ChoiceField(choices=METRIC_CODES, allow_null=True)


class ReportRunSerializer(RunSummarySerializer):
    metrics = ReportMetricSerializer(many=True)
    issues = ReportIssueSerializer(many=True)


class ReportDetailSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    title = serializers.CharField()
    notes = serializers.CharField(allow_blank=True, help_text="The user's own commentary.")
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
    runs = ReportRunSerializer(many=True)


def report_summary(report: Report) -> dict[str, Any]:
    """Expects the ``run_count`` annotation."""
    return {
        "id": report.public_id,
        "title": report.title,
        "run_count": report.run_count,  # type: ignore[attr-defined]
        "created_at": report.created_at,
        "updated_at": report.updated_at,
    }


def report_detail(
    report: Report,
    runs: list[AnalysisRun],
    metrics: list[MetricResult],
    issues: list[AnalysisIssue],
) -> dict[str, Any]:
    """The report with each run, rendered live from its stored results.

    ``notes`` is the user's commentary; every figure comes from a run.
    """
    metrics_by_run: dict[int, list[dict[str, Any]]] = {}
    for metric in metrics:
        metrics_by_run.setdefault(metric.run_id, []).append(
            {
                "code": metric.metric_code,
                "name": _NAMES.get(metric.metric_code, metric.metric_code),
                "value": None if metric.value is None else format(metric.value, "f"),
                "unit": metric.unit,
            }
        )
    issues_by_run: dict[int, list[dict[str, Any]]] = {}
    for issue in issues:
        issues_by_run.setdefault(issue.run_id, []).append(
            {**issue_data(issue), "metric_code": issue.metric_code or None}
        )
    return {
        "id": report.public_id,
        "title": report.title,
        "notes": report.notes,
        "created_at": report.created_at,
        "updated_at": report.updated_at,
        "runs": [
            {
                **run_summary(run),
                "metrics": metrics_by_run.get(run.pk, []),
                "issues": issues_by_run.get(run.pk, []),
            }
            for run in runs
        ],
    }
