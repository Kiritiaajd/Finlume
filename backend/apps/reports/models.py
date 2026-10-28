"""Report and its ordered runs (DATA_MODEL §4.12).

A report stores no calculated values. It is rendered live from the runs it
lists, which are immutable, so it can never drift from them. ``notes`` is the
user's commentary, kept apart from the calculated figures.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import F

from apps.analysis.models import AnalysisRun
from apps.core.models import PublicModel
from apps.workspaces.models import Workspace


class Report(PublicModel):
    # No separate index: the (workspace, created_at) index leads with it.
    workspace = models.ForeignKey(
        Workspace, on_delete=models.CASCADE, related_name="reports", db_index=False
    )
    title = models.CharField(max_length=200)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    runs: models.ManyToManyField[AnalysisRun, ReportRun] = models.ManyToManyField(
        AnalysisRun, through="ReportRun", related_name="reports"
    )

    class Meta:
        constraints = [
            # Composite foreign key target: a report's runs are in its workspace.
            models.UniqueConstraint(
                fields=["workspace", "id"], name="reports_report_workspace_key"
            ),
        ]
        indexes = [
            models.Index("workspace", F("created_at").desc(), name="report_ws_created_idx"),
        ]

    def __str__(self) -> str:
        return self.title


class ReportRun(models.Model):
    """One run in a report, at its position. A run in a report cannot be deleted."""

    # The workspace is repeated here so that, on PostgreSQL, composite foreign
    # keys can tie both the report and the run to it (migration 0002).
    workspace = models.ForeignKey(
        Workspace, on_delete=models.CASCADE, related_name="+", db_index=False
    )
    report = models.ForeignKey(Report, on_delete=models.CASCADE, db_index=False)
    run = models.ForeignKey(AnalysisRun, on_delete=models.RESTRICT, related_name="+")
    position = models.PositiveSmallIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["report", "run"], name="reports_reportrun_run_unique"),
            models.UniqueConstraint(
                fields=["report", "position"], name="reports_reportrun_position_unique"
            ),
        ]

    def __str__(self) -> str:
        return f"report {self.report_id} #{self.position}: run {self.run_id}"
