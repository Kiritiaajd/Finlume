"""Request and response shapes for reports."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.analysis.api.serializers import issue_data, run_summary
from apps.analysis.models import AnalysisIssue, AnalysisRun, MetricResult
from apps.reports.models import Report
from domain.calculations import RATIO_DEFINITIONS

_NAMES = {definition.code: definition.name for definition in RATIO_DEFINITIONS}


class ReportInputSerializer(serializers.Serializer[Any]):
    """Create a report, or (``partial=True``) change part of one."""

    title = serializers.CharField(max_length=200)
    notes = serializers.CharField(max_length=10_000, allow_blank=True, default="")
    run_ids = serializers.ListField(child=serializers.UUIDField(), default=list)


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
