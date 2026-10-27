"""Runs are immutable, keep their inputs, and go only with their workspace."""

from __future__ import annotations

import pytest
from django.db import IntegrityError, connection, transaction
from django.db.models import RestrictedError
from django.urls import reverse

from apps.analysis.models import (
    AnalysisIssue,
    AnalysisRun,
    AnalysisRunInputFact,
    ImmutableRecordError,
    MetricResult,
)
from apps.financial_records.models import FinancialFact
from services.statement_analysis import run_analysis

from .conftest import BALANCE, FY2025, INCOME

pytestmark = pytest.mark.django_db


@pytest.fixture
def run(validated, owner, workspace, entity):
    validated("income_statement", INCOME)
    validated("balance_sheet", BALANCE)
    return run_analysis(actor=owner, workspace=workspace, entity=entity, period=FY2025)


def test_a_run_records_its_metrics_issues_and_exact_inputs(run):
    assert run.metrics.count() == 7
    assert run.input_facts.count() == len(INCOME) + len(BALANCE)
    assert set(run.input_facts.all()) == set(FinancialFact.objects.all())


@pytest.mark.parametrize("model", [AnalysisRun, MetricResult, AnalysisRunInputFact])
def test_saved_records_cannot_be_changed(run, model):
    record = model.objects.first()

    with pytest.raises(ImmutableRecordError):
        record.save()


@pytest.mark.parametrize("model", [AnalysisRun, MetricResult, AnalysisRunInputFact])
def test_records_cannot_be_deleted_one_by_one(run, model):
    with pytest.raises(ImmutableRecordError):
        model.objects.first().delete()


def test_a_fact_a_run_used_cannot_be_deleted(run):
    with pytest.raises(RestrictedError):
        FinancialFact.objects.get(line_item="revenue").delete()


def test_the_entity_of_a_run_cannot_be_deleted(run):
    with pytest.raises(RestrictedError):
        run.entity.delete()


def test_deleting_the_workspace_deletes_its_runs(run, workspace):
    workspace.delete()

    assert not AnalysisRun.objects.exists()
    assert not MetricResult.objects.exists()
    assert not AnalysisIssue.objects.exists()
    assert not AnalysisRunInputFact.objects.exists()
    connection.check_constraints()


@pytest.mark.parametrize(
    ("field", "value", "constraint"),
    [
        ("input_fingerprint", "ABC", "fingerprint_format"),
        ("currency", "usd", "currency_format"),
        ("period_type", "weekly", "period_type_valid"),
    ],
)
def test_run_columns_are_checked_by_the_database(run, field, value, constraint):
    fields = {
        "workspace": run.workspace,
        "entity": run.entity,
        "period_start": run.period_start,
        "period_end": run.period_end,
        "period_type": run.period_type,
        "currency": run.currency,
        "engine_version": run.engine_version,
        "input_fingerprint": run.input_fingerprint,
        field: value,
    }

    with pytest.raises(IntegrityError, match=constraint), transaction.atomic():
        AnalysisRun.objects.create(**fields)


@pytest.mark.parametrize(
    ("fields", "constraint"),
    [
        ({"metric_code": "ebitda_margin"}, "metric_code_valid"),
        ({"unit": "percent"}, "unit_valid"),
    ],
)
def test_metric_codes_and_units_are_checked(run, fields, constraint):
    # A run without metrics, so only the constraint under test can fail.
    empty = AnalysisRun.objects.create(
        workspace=run.workspace,
        entity=run.entity,
        period_start=run.period_start,
        period_end=run.period_end,
        period_type=run.period_type,
        currency=run.currency,
        engine_version=run.engine_version,
        input_fingerprint=run.input_fingerprint,
    )
    values = {"metric_code": "gross_margin", "unit": "ratio", **fields}

    with pytest.raises(IntegrityError, match=constraint), transaction.atomic():
        MetricResult.objects.create(run=empty, position=0, methodology="x", **values)


@pytest.mark.postgres
def test_a_run_cannot_use_an_entity_from_another_workspace(run, make_workspace):
    def create_and_check():
        AnalysisRun.objects.create(
            workspace=make_workspace(),
            entity=run.entity,
            period_start=run.period_start,
            period_end=run.period_end,
            period_type=run.period_type,
            currency=run.currency,
            engine_version=run.engine_version,
            input_fingerprint=run.input_fingerprint,
        )
        connection.check_constraints()  # the composite key is deferred

    with pytest.raises(IntegrityError, match="entity_same_workspace"), transaction.atomic():
        create_and_check()


def test_the_admin_is_view_only(admin_client, run):
    change = reverse("admin:analysis_analysisrun_change", args=[run.pk])

    assert admin_client.get(reverse("admin:analysis_analysisrun_changelist")).status_code == 200
    assert admin_client.get(reverse("admin:analysis_analysisrun_add")).status_code == 403
    page = admin_client.get(change)
    assert page.status_code == 200
    assert b'name="_save"' not in page.content
