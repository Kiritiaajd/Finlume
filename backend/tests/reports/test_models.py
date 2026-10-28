"""Reports keep their runs, stay in one workspace, and go with their workspace."""

from __future__ import annotations

import pytest
from django.db import IntegrityError, connection, transaction
from django.db.models import RestrictedError
from django.urls import reverse

from apps.analysis.models import AnalysisRun
from apps.reports.models import Report, ReportRun

pytestmark = pytest.mark.django_db


@pytest.fixture
def report(workspace, make_run):
    report = Report.objects.create(workspace=workspace, title="Review")
    ReportRun.objects.create(workspace=workspace, report=report, run=make_run(), position=0)
    return report


def test_a_run_in_a_report_cannot_be_deleted_even_by_a_bulk_delete(report):
    # Single deletes are refused by the run itself; RESTRICT also stops a queryset delete.
    with pytest.raises(RestrictedError):
        AnalysisRun.objects.all().delete()


def test_deleting_the_workspace_deletes_its_reports(report, workspace):
    workspace.delete()

    assert not Report.objects.exists()
    assert not ReportRun.objects.exists()
    connection.check_constraints()


def test_a_run_appears_once_and_positions_are_unique(report, make_run):
    run = report.runs.get()

    with pytest.raises(IntegrityError), transaction.atomic():
        ReportRun.objects.create(workspace=report.workspace, report=report, run=run, position=1)
    with pytest.raises(IntegrityError), transaction.atomic():
        ReportRun.objects.create(
            workspace=report.workspace, report=report, run=make_run(), position=0
        )


@pytest.mark.postgres
@pytest.mark.parametrize("mismatch", ["report", "run"])
def test_a_report_and_its_runs_share_one_workspace(workspace, make_workspace, make_run, mismatch):
    # The report is in ``elsewhere`` and the run in ``workspace``; the link
    # matches one of them, so exactly one composite key is broken.
    elsewhere = make_workspace()
    report = Report.objects.create(workspace=elsewhere, title="Review")
    run = make_run()
    link_workspace = workspace if mismatch == "report" else elsewhere

    def link_and_check():
        ReportRun.objects.create(workspace=link_workspace, report=report, run=run, position=0)
        connection.check_constraints()  # the composite keys are deferred

    expected = "report_same_workspace" if mismatch == "report" else "run_same_workspace"
    with pytest.raises(IntegrityError, match=expected), transaction.atomic():
        link_and_check()


def test_the_admin_is_view_only(admin_client, report):
    page = admin_client.get(reverse("admin:reports_report_change", args=[report.pk]))

    assert admin_client.get(reverse("admin:reports_report_changelist")).status_code == 200
    assert admin_client.get(reverse("admin:reports_report_add")).status_code == 403
    assert page.status_code == 200
    assert b'name="_save"' not in page.content
