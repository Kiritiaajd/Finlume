"""Saved reports over analysis runs (MVP step 5b).

A report holds a title, the user's notes and an ordered list of runs from its
own workspace. It stores no figures: it is rendered from the immutable runs.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from django.db import transaction

from apps.accounts.models import User
from apps.analysis.models import AnalysisRun
from apps.audit.models import AuditEvent
from apps.reports.models import Report, ReportRun
from apps.workspaces.models import Workspace
from services.errors import InvalidInput

MAX_RUNS_PER_REPORT = 50


@transaction.atomic
def create_report(
    *, actor: User, workspace: Workspace, title: str, notes: str, run_ids: Sequence[UUID]
) -> Report:
    runs = _runs_in_workspace(workspace, run_ids)
    report = Report.objects.create(workspace=workspace, title=title, notes=notes, created_by=actor)
    _set_runs(report, runs)
    AuditEvent.record(
        "report.created", actor=actor, workspace=workspace, target=report, runs=len(runs)
    )
    return report


@transaction.atomic
def update_report(
    *,
    actor: User,
    workspace: Workspace,
    report: Report,
    title: str | None = None,
    notes: str | None = None,
    run_ids: Sequence[UUID] | None = None,
) -> Report:
    """Change what was sent; ``run_ids`` replaces the whole ordered list."""
    locked = Report.objects.select_for_update().get(pk=report.pk)
    runs = None if run_ids is None else _runs_in_workspace(workspace, run_ids)
    changed: list[str] = []
    if title is not None:
        locked.title = title
        changed.append("title")
    if notes is not None:
        locked.notes = notes
        changed.append("notes")
    locked.save(update_fields=[*changed, "updated_at"])
    if runs is not None:
        ReportRun.objects.filter(report=locked).delete()
        _set_runs(locked, runs)
        changed.append("runs")
    AuditEvent.record(
        "report.updated", actor=actor, workspace=workspace, target=locked, fields=changed
    )
    return locked


def _runs_in_workspace(workspace: Workspace, run_ids: Sequence[UUID]) -> list[AnalysisRun]:
    """The runs, in the order given. An ID outside the workspace is not found."""
    if len(run_ids) > MAX_RUNS_PER_REPORT:
        raise InvalidInput({"run_ids": [f"A report has at most {MAX_RUNS_PER_REPORT} runs."]})
    if len(set(run_ids)) != len(run_ids):
        raise InvalidInput({"run_ids": ["Each run can appear only once."]})
    found = {
        run.public_id: run
        for run in AnalysisRun.objects.filter(workspace=workspace, public_id__in=run_ids)
    }
    missing = [str(run_id) for run_id in run_ids if run_id not in found]
    if missing:
        # The same answer for another workspace's run as for none at all.
        raise InvalidInput(
            {"run_ids": [f"No run {run_id} in this workspace." for run_id in missing]}
        )
    return [found[run_id] for run_id in run_ids]


def _set_runs(report: Report, runs: list[AnalysisRun]) -> None:
    ReportRun.objects.bulk_create(
        ReportRun(workspace_id=report.workspace_id, report=report, run=run, position=position)
        for position, run in enumerate(runs)
    )
