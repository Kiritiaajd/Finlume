"""AnalysisRun, MetricResult and AnalysisIssue (DATA_MODEL §4.9 to 4.11).

A run is append-only: once saved, it and its results are never changed, so
it reloads with identical values (FR-033, FR-034). A correction is a new
statement version and a new run. The rows can only disappear together with
their workspace.
"""

from __future__ import annotations

import uuid
from typing import Any

from django.conf import settings
from django.db import models
from django.db.models import Exists, F, OuterRef, Q, QuerySet

from apps.financial_records.models import (
    PERIOD_TYPES,
    FinancialFact,
    ReportingEntity,
    StatementStatus,
)
from apps.workspaces.models import Workspace
from domain.calculations import RATIO_DEFINITIONS, MetricUnit
from domain.validation import IssueCode, Severity

METRIC_CODES = [definition.code for definition in RATIO_DEFINITIONS]
UNITS = [unit.value for unit in MetricUnit]
ISSUE_CODES = [code.value for code in IssueCode]
SEVERITIES = [severity.value for severity in Severity]


class ImmutableRecordError(RuntimeError):
    """Raised when code tries to change or delete a saved analysis record."""


class _AppendOnly(models.Model):
    """Rows that can be created, but never updated or deleted one by one."""

    class Meta:
        abstract = True

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise ImmutableRecordError(f"A saved {self._meta.model_name} cannot be changed.")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise ImmutableRecordError(f"A {self._meta.model_name} is deleted only with its workspace.")


class AnalysisRun(_AppendOnly):
    """One execution of ``domain.calculations.run_statement_analysis``."""

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    workspace = models.ForeignKey(
        Workspace, on_delete=models.CASCADE, related_name="analysis_runs", db_index=False
    )
    entity = models.ForeignKey(
        ReportingEntity, on_delete=models.RESTRICT, related_name="analysis_runs", db_index=False
    )
    period_start = models.DateField()
    period_end = models.DateField()
    period_type = models.CharField(max_length=16)
    currency = models.CharField(max_length=3)
    engine_version = models.CharField(max_length=32)
    input_fingerprint = models.CharField(max_length=64)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    # The client's Idempotency-Key for the request that created this run.
    idempotency_key = models.UUIDField(null=True, blank=True)
    input_facts: models.ManyToManyField[FinancialFact, AnalysisRunInputFact] = (
        models.ManyToManyField(
            FinancialFact, through="AnalysisRunInputFact", related_name="analysis_runs"
        )
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(period_start__lte=F("period_end")),
                name="analysis_analysisrun_period_order",
            ),
            models.CheckConstraint(
                condition=Q(period_type__in=PERIOD_TYPES),
                name="analysis_analysisrun_period_type_valid",
            ),
            models.CheckConstraint(
                condition=Q(currency__regex=r"^[A-Z]{3}$"),
                name="analysis_analysisrun_currency_format",
            ),
            models.CheckConstraint(
                condition=Q(input_fingerprint__regex=r"^[0-9a-f]{64}$"),
                name="analysis_analysisrun_fingerprint_format",
            ),
            models.UniqueConstraint(
                fields=["workspace", "created_by", "idempotency_key"],
                condition=Q(idempotency_key__isnull=False),
                name="analysis_analysisrun_idempotency_unique",
            ),
            # Composite foreign key target: a report and its runs share one
            # workspace (reports migration 0002).
            models.UniqueConstraint(
                fields=["workspace", "id"], name="analysis_analysisrun_workspace_key"
            ),
        ]
        indexes = [
            models.Index(
                "workspace", "entity", F("created_at").desc(), name="run_ws_entity_created_idx"
            ),
            # Finds runs equivalent to this one (same inputs, same engine).
            models.Index(
                fields=["entity", "input_fingerprint", "engine_version"],
                name="run_entity_fp_engine_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"run {self.public_id} ({self.period_start}..{self.period_end})"


class AnalysisRunInputFact(_AppendOnly):
    """Exactly which facts a run used. A fact a run used cannot be deleted."""

    run = models.ForeignKey(AnalysisRun, on_delete=models.CASCADE, db_index=False)
    fact = models.ForeignKey(FinancialFact, on_delete=models.RESTRICT, related_name="+")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["run", "fact"], name="analysis_analysisruninputfact_unique"
            ),
        ]

    def __str__(self) -> str:
        return f"run {self.run_id} used fact {self.fact_id}"


class MetricResult(_AppendOnly):
    """One metric of a run, with the methodology and inputs it was computed from."""

    run = models.ForeignKey(
        AnalysisRun, on_delete=models.CASCADE, related_name="metrics", db_index=False
    )
    position = models.PositiveSmallIntegerField()  # report order
    metric_code = models.CharField(max_length=64)
    value = models.DecimalField(max_digits=24, decimal_places=6, null=True, blank=True)
    unit = models.CharField(max_length=16)
    methodology = models.TextField()
    # {line_item_code: "decimal string"}; never JSON numbers.
    inputs = models.JSONField(default=dict)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["run", "metric_code"], name="analysis_metricresult_unique"
            ),
            models.CheckConstraint(
                condition=Q(metric_code__in=METRIC_CODES),
                name="analysis_metricresult_metric_code_valid",
            ),
            models.CheckConstraint(
                condition=Q(unit__in=UNITS), name="analysis_metricresult_unit_valid"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.metric_code} = {self.value}"


class AnalysisIssue(_AppendOnly):
    """A validation or calculation issue of a run."""

    run = models.ForeignKey(
        AnalysisRun, on_delete=models.CASCADE, related_name="issues", db_index=False
    )
    position = models.PositiveSmallIntegerField()
    # Blank for validation issues about the whole fact set.
    metric_code = models.CharField(max_length=64, blank=True)
    code = models.CharField(max_length=64)
    severity = models.CharField(max_length=16)
    message = models.TextField()
    line_items = models.JSONField(default=list)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["run", "position"], name="analysis_analysisissue_position_unique"
            ),
            models.CheckConstraint(
                condition=Q(code__in=ISSUE_CODES), name="analysis_analysisissue_code_valid"
            ),
            models.CheckConstraint(
                condition=Q(severity__in=SEVERITIES),
                name="analysis_analysisissue_severity_valid",
            ),
            models.CheckConstraint(
                condition=Q(metric_code="") | Q(metric_code__in=METRIC_CODES),
                name="analysis_analysisissue_metric_code_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


def with_superseded_flag(runs: QuerySet[AnalysisRun]) -> QuerySet[AnalysisRun]:
    """Annotate ``uses_superseded_statement``: a statement the run used was restated since.

    The run stays valid for the figures it used; a new run would differ. One
    subquery, so it costs no extra round trip.
    """
    superseded = AnalysisRunInputFact.objects.filter(
        run=OuterRef("pk"), fact__statement__status=StatementStatus.SUPERSEDED
    )
    return runs.annotate(uses_superseded_statement=Exists(superseded))
