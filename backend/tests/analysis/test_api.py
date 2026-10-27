"""Running and reading analyses (MVP step 5a; acceptance criteria 6, 7 and 9)."""

from __future__ import annotations

import uuid

import pytest

from apps.analysis.models import AnalysisRun
from apps.audit.models import AuditEvent
from apps.financial_records.models import StatementStatus
from apps.workspaces.models import WorkspaceRole
from domain.calculations import ENGINE_VERSION, fingerprint
from services.statement_analysis import (
    assemble_analysis_input,
    restate_statement,
    validate_statement,
)

from .conftest import BALANCE, FY2025, INCOME

pytestmark = pytest.mark.django_db

PERIOD = {"period_start": "2025-01-01", "period_end": "2025-12-31", "period_type": "annual"}


@pytest.fixture
def client(api_client, owner):
    api_client.force_login(owner)
    return api_client


def runs_url(workspace, entity):
    return f"/api/v1/workspaces/{workspace.public_id}/entities/{entity.public_id}/analyses/"


def run_url(workspace, run_id):
    return f"/api/v1/workspaces/{workspace.public_id}/analyses/{run_id}/"


@pytest.fixture
def analyse(client, workspace, entity):
    def post(body=None, headers=None):
        return client.post(
            runs_url(workspace, entity), body or PERIOD, format="json", headers=headers or {}
        )

    return post


# --- Acceptance criterion 6 ------------------------------------------------------------------


def test_a_run_shows_all_seven_ratios_with_methodology_and_inputs(validated, analyse):
    validated("income_statement", INCOME)
    validated("balance_sheet", BALANCE)

    response = analyse()

    body = response.json()
    assert response.status_code == 201, body
    assert (body["currency"], body["engine_version"]) == ("USD", ENGINE_VERSION)
    assert [(m["code"], m["value"]) for m in body["metrics"]] == [
        ("gross_margin", "0.400000"),
        ("operating_margin", "0.150000"),
        ("net_margin", "0.100000"),
        ("current_ratio", "2.000000"),
        ("debt_to_equity", "0.600000"),
        ("return_on_equity", "0.200000"),
        ("return_on_assets", "0.083333"),
    ]
    roe = body["metrics"][5]
    assert roe["name"] == "Return on equity"
    assert "closing total equity" in roe["methodology"]
    assert roe["inputs"] == {"net_income": "100000.000000", "total_equity": "500000.000000"}
    assert roe["unit"] == "ratio"
    assert body["issues"] == []


def test_a_missing_input_is_not_computable_never_zero(validated, analyse):
    validated("income_statement", INCOME)  # no balance sheet

    metrics = {m["code"]: m for m in analyse().json()["metrics"]}

    current = metrics["current_ratio"]
    assert current["value"] is None
    assert [i["code"] for i in current["issues"]] == ["missing_input"]
    assert current["issues"][0]["line_items"] == [
        "total_current_assets",
        "total_current_liabilities",
    ]
    assert metrics["gross_margin"]["value"] == "0.400000"


def test_validation_warnings_are_kept_with_the_run(validated, analyse):
    validated("income_statement", INCOME)
    validated("balance_sheet", {**BALANCE, "total_assets": "1300"})  # does not balance

    body = analyse().json()

    assert [i["code"] for i in body["issues"]] == ["balance_sheet_imbalance"]
    assert len(body["metrics"]) == 7  # a warning never blocks the analysis


# --- Acceptance criterion 7 ------------------------------------------------------------------


def test_a_saved_run_reloads_identically_and_reruns_reproduce_it(
    client, workspace, entity, validated, analyse
):
    validated("income_statement", INCOME)
    validated("balance_sheet", BALANCE)

    first = analyse().json()
    reloaded = client.get(run_url(workspace, first["id"])).json()
    second = analyse().json()

    assert reloaded == first
    assert second["id"] != first["id"]  # every run is kept
    assert second["input_fingerprint"] == first["input_fingerprint"]
    assert second["metrics"] == first["metrics"]
    assert first["input_fingerprint"] == fingerprint(
        assemble_analysis_input(entity=entity, period=FY2025).facts
    )


def test_every_input_traces_to_its_row_statement_version_and_document(validated, analyse):
    income = validated("income_statement", INCOME)

    inputs = analyse().json()["inputs"]

    revenue = next(i for i in inputs if i["line_item"] == "revenue")
    row = income.line_items.get(line_item_code="revenue")
    assert revenue == {
        "line_item": "revenue",
        "value": "1000000.000000",
        "row_id": str(row.public_id),
        "statement_id": str(income.public_id),
        "statement_version": 1,
        "document_id": str(income.source_document.public_id),
    }
    assert sorted(i["line_item"] for i in inputs) == sorted(INCOME)


def test_a_restated_statement_flags_earlier_runs_and_leaves_them_unchanged(
    client, workspace, owner, validated, analyse
):
    income = validated("income_statement", INCOME)
    first = analyse().json()
    draft = restate_statement(actor=owner, workspace=workspace, statement=income, reason="Fix")
    draft.line_items.filter(line_item_code="net_income").update(
        reported_amount="120", raw_value="120"
    )
    validate_statement(actor=owner, workspace=workspace, statement=draft)

    second = analyse().json()
    reloaded = client.get(run_url(workspace, first["id"])).json()

    assert reloaded["uses_superseded_statement"] is True
    assert reloaded["metrics"] == first["metrics"]  # the earlier run keeps its figures
    assert second["uses_superseded_statement"] is False
    assert second["input_fingerprint"] != first["input_fingerprint"]
    net_margin = {m["code"]: m["value"] for m in second["metrics"]}["net_margin"]
    assert net_margin == "0.120000"


# --- Refusals ---------------------------------------------------------------------------------


def test_a_period_without_a_validated_statement_is_refused_and_nothing_saved(
    entity, make_statement, analyse
):
    make_statement(entity=entity, status=StatementStatus.DRAFT)

    response = analyse()

    assert response.status_code == 409
    assert not AnalysisRun.objects.exists()


def test_statements_in_different_currencies_are_refused_and_nothing_saved(validated, analyse):
    validated("income_statement", INCOME)
    validated("balance_sheet", BALANCE, currency="EUR")

    response = analyse()

    assert response.status_code == 409
    assert "EUR, USD" in response.json()["error"]["message"]
    assert not AnalysisRun.objects.exists()


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({**PERIOD, "period_end": "2024-12-31"}, "period_end"),
        ({**PERIOD, "period_type": "weekly"}, "period_type"),
        ({"period_start": "2025-01-01"}, "period_end"),
    ],
)
def test_an_invalid_period_is_rejected(analyse, body, field):
    response = analyse(body)

    assert response.status_code == 400
    assert field in response.json()["error"]["details"]


# --- Idempotency and audit --------------------------------------------------------------------


def test_replaying_an_idempotency_key_returns_the_original_run(validated, analyse):
    validated("income_statement", INCOME)
    key = str(uuid.uuid4())

    first = analyse(headers={"Idempotency-Key": key})
    again = analyse(headers={"Idempotency-Key": key})

    assert (first.status_code, again.status_code) == (201, 201)
    assert again.json() == first.json()
    assert AnalysisRun.objects.count() == 1


def test_an_idempotency_key_reused_for_another_period_is_a_conflict(validated, analyse):
    validated("income_statement", INCOME)
    key = str(uuid.uuid4())
    analyse(headers={"Idempotency-Key": key})

    response = analyse({**PERIOD, "period_type": "other"}, headers={"Idempotency-Key": key})

    assert response.status_code == 409


def test_an_idempotency_key_must_be_a_uuid(validated, analyse):
    validated("income_statement", INCOME)

    assert analyse(headers={"Idempotency-Key": "again"}).status_code == 400
    assert not AnalysisRun.objects.exists()


def test_running_an_analysis_is_audited_without_figures(validated, analyse):
    validated("income_statement", INCOME)

    run_id = analyse().json()["id"]

    event = AuditEvent.objects.get(action="analysis.run")
    assert str(event.target_public_id) == run_id
    assert event.metadata == {"engine_version": ENGINE_VERSION, "facts": 5, "issues": 4}


# --- Access and query budgets -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("role", "get_status", "post_status"),
    [(None, 404, 404), (WorkspaceRole.VIEWER, 200, 403), (WorkspaceRole.EDITOR, 200, 201)],
)
def test_viewers_read_and_editors_run(
    api_client,
    workspace,
    entity,
    validated,
    add_to_workspace,
    make_user,
    role,
    get_status,
    post_status,
):
    validated("income_statement", INCOME)
    api_client.force_login(make_user() if role is None else add_to_workspace(workspace, role))

    assert api_client.get(runs_url(workspace, entity)).status_code == get_status
    assert (
        api_client.post(runs_url(workspace, entity), PERIOD, format="json").status_code
        == post_status
    )


def test_anonymous_callers_get_401(api_client, workspace, entity):
    assert api_client.get(runs_url(workspace, entity)).status_code == 401
    assert api_client.post(runs_url(workspace, entity), PERIOD, format="json").status_code == 401


def test_another_workspaces_entity_and_runs_are_not_found(
    client, workspace, make_entity, make_workspace, validated, analyse
):
    validated("income_statement", INCOME)
    run_id = analyse().json()["id"]
    elsewhere = make_workspace()
    other_owner = elsewhere.memberships.get().user
    client.force_login(other_owner)

    assert client.get(run_url(elsewhere, run_id)).status_code == 404
    assert client.get(runs_url(elsewhere, make_entity(workspace=workspace))).status_code == 404
    assert (
        client.get(f"/api/v1/workspaces/{elsewhere.public_id}/analyses/{uuid.uuid4()}/").status_code
        == 404
    )


def test_listing_runs_costs_four_queries(
    client, workspace, entity, validated, analyse, assert_app_queries
):
    validated("income_statement", INCOME)
    analyse()
    analyse()

    with assert_app_queries(4):  # access + entity + count + page (staleness in a subquery)
        response = client.get(runs_url(workspace, entity))

    assert response.json()["count"] == 2


def test_a_run_costs_five_queries(client, workspace, validated, analyse, assert_app_queries):
    validated("income_statement", INCOME)
    run_id = analyse().json()["id"]

    with assert_app_queries(5):  # access + run + metrics + issues + traced inputs
        client.get(run_url(workspace, run_id))
