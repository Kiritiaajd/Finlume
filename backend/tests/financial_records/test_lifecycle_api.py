"""Validating drafts and restating statements (MVP step 3b).

Acceptance criteria 5 (warnings never block) and 8 (a correction is version 2,
and version 1 keeps its figures).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.audit.models import AuditEvent
from apps.financial_records.models import FinancialFact, FinancialStatement, StatementStatus
from apps.workspaces.models import WorkspaceRole
from domain.financial_statements import LineItem, PeriodType, ReportingPeriod
from services.statement_analysis import assemble_analysis_input

pytestmark = pytest.mark.django_db

VALIDATED, DRAFT, SUPERSEDED = (
    StatementStatus.VALIDATED,
    StatementStatus.DRAFT,
    StatementStatus.SUPERSEDED,
)
FY = ReportingPeriod(date(2025, 4, 1), date(2026, 3, 31), PeriodType.ANNUAL)


@pytest.fixture
def workspace(make_workspace):
    return make_workspace()


@pytest.fixture
def entity(workspace, make_entity):
    return make_entity(workspace=workspace, name="Example Lending Co")


@pytest.fixture
def client(api_client, workspace, add_to_workspace):
    api_client.force_login(add_to_workspace(workspace, WorkspaceRole.EDITOR))
    return api_client


def row(code, amount, label=None):
    return {"label": label or code, "line_item_code": code, "amount": amount}


@pytest.fixture
def draft(client, workspace, entity):
    """Create a draft through the API; returns its JSON."""

    def create(statement_type="income_statement", line_items=None, scale="crores"):
        response = client.post(
            f"/api/v1/workspaces/{workspace.public_id}/entities/{entity.public_id}/statements/",
            {
                "statement_type": statement_type,
                "period_start": "2025-04-01",
                "period_end": "2026-03-31",
                "period_type": "annual",
                "currency": "INR",
                "reported_scale": scale,
                "line_items": line_items
                if line_items is not None
                else [row("revenue", "1250.5"), row("net_income", "125")],
            },
            format="json",
        )
        assert response.status_code == 201, response.json()
        return response.json()

    return create


@pytest.fixture
def act(client, workspace):
    """POST a statement action (``validate`` or ``restatements``)."""

    def post(statement, action, body=None):
        url = f"/api/v1/workspaces/{workspace.public_id}/statements/{statement['id']}/{action}/"
        return client.post(url, body or {}, format="json")

    return post


@pytest.fixture
def validated(draft, act):
    def create(*args, **kwargs):
        response = act(draft(*args, **kwargs), "validate")
        assert response.status_code == 200, response.json()
        return response.json()

    return create


def get_statement(client, workspace, statement):
    return client.get(f"/api/v1/workspaces/{workspace.public_id}/statements/{statement['id']}/")


# --- Validating ----------------------------------------------------------------------------


def test_validating_saves_the_facts_in_base_units(client, workspace, draft, act):
    statement = draft(
        line_items=[
            row("revenue", "1250.5", "Revenue from operations"),
            row("", "3", "Memo line"),  # unmapped: no fact
            row("cost_of_revenue", None),  # blank: no fact
            row("net_income", "-12.25"),  # a loss keeps its sign
        ]
    )

    response = act(statement, "validate")

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "validated"
    assert [(f["line_item"], f["value"]) for f in body["facts"]] == [
        ("revenue", "12505000000.000000"),  # 1,250.5 crores
        ("net_income", "-122500000.000000"),
    ]
    assert body["facts"][0]["row_id"] == body["line_items"][0]["id"]
    assert {f["review_status"] for f in body["facts"]} == {"confirmed"}
    fact = FinancialFact.objects.get(line_item="revenue")
    assert fact.reviewed_by is not None
    assert fact.reviewed_at is not None
    assert AuditEvent.objects.filter(action="statement.validated").exists()
    # The facts stay on the statement.
    assert get_statement(client, workspace, statement).json()["facts"] == body["facts"]


def test_warnings_are_returned_and_never_block(draft, act):
    # MVP acceptance criterion 5.
    balance = draft(
        "balance_sheet",
        [row("total_assets", "100"), row("total_liabilities", "60"), row("total_equity", "30")],
    )
    income = draft("income_statement", [row("revenue", "-5")])

    balance_issues = act(balance, "validate").json()["issues"]
    income_issues = act(income, "validate").json()["issues"]

    assert [i["code"] for i in balance_issues] == ["balance_sheet_imbalance"]
    assert balance_issues[0]["severity"] == "warning"
    assert balance_issues[0]["line_items"] == ["total_assets", "total_liabilities", "total_equity"]
    assert [i["code"] for i in income_issues] == ["unexpected_sign"]
    assert FinancialStatement.objects.filter(status=VALIDATED).count() == 2


def test_a_clean_statement_has_no_issues(draft, act):
    assert act(draft(), "validate").json()["issues"] == []


@pytest.mark.parametrize("status", [VALIDATED, SUPERSEDED])
def test_only_a_draft_can_be_validated(entity, make_statement, act, status):
    statement = make_statement(entity=entity, status=status)

    response = act({"id": statement.public_id}, "validate")

    assert response.status_code == 409


def test_a_draft_without_any_figure_cannot_be_validated(draft, act):
    statement = draft(line_items=[row("", "5", "Memo"), row("revenue", None)])

    response = act(statement, "validate")

    assert response.status_code == 409
    assert FinancialStatement.objects.get(public_id=statement["id"]).status == DRAFT
    assert not FinancialFact.objects.exists()


def test_a_validated_statement_can_no_longer_be_edited(client, workspace, validated):
    statement = validated()

    response = client.patch(
        f"/api/v1/workspaces/{workspace.public_id}/statements/{statement['id']}/",
        {"currency": "USD"},
        format="json",
    )

    assert response.status_code == 409


# --- Restating -----------------------------------------------------------------------------


def test_restating_starts_version_2_from_a_copy_of_the_rows(validated, act):
    v1 = validated()

    response = act(v1, "restatements", {"reason": "  Auditor adjustment  "})

    v2 = response.json()
    assert response.status_code == 201
    assert (v2["status"], v2["version"], v2["supersedes_id"]) == ("draft", 2, v1["id"])
    assert v2["restatement_reason"] == "Auditor adjustment"
    assert [(r["line_item_code"], r["raw_value"]) for r in v2["line_items"]] == [
        (r["line_item_code"], r["raw_value"]) for r in v1["line_items"]
    ]
    assert v2["facts"] == []
    assert AuditEvent.objects.filter(action="statement.restated").exists()


def test_a_restatement_can_bring_new_rows(validated, act):
    v1 = validated()

    response = act(v1, "restatements", {"reason": "Typo", "line_items": [row("revenue", "1300")]})

    assert response.status_code == 201
    assert [r["raw_value"] for r in response.json()["line_items"]] == ["1300"]


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({}, "reason"),
        ({"reason": "   "}, "reason"),
        ({"reason": "x", "line_items": [row("total_assets", "1")]}, "line_items"),
        ({"reason": "x", "line_items": [row("revenue", "1e21")]}, "line_items"),  # crores
    ],
    ids=["no reason", "blank reason", "wrong statement type", "too large once scaled"],
)
def test_restatement_input_is_validated(validated, act, body, field):
    response = act(validated(), "restatements", body)

    assert response.status_code == 400
    assert field in response.json()["error"]["details"]
    assert FinancialStatement.objects.count() == 1


@pytest.mark.parametrize("status", [DRAFT, SUPERSEDED])
def test_only_the_validated_version_can_be_restated(entity, make_statement, act, status):
    statement = make_statement(entity=entity, status=status)

    assert act({"id": statement.public_id}, "restatements", {"reason": "x"}).status_code == 409


def test_one_restatement_at_a_time(validated, act):
    v1 = validated()
    act(v1, "restatements", {"reason": "First"})

    response = act(v1, "restatements", {"reason": "Second"})

    assert response.status_code == 409
    assert "already has a restatement in progress" in response.json()["error"]["message"]


# --- The whole correction (acceptance criterion 8) -----------------------------------------


def test_a_correction_supersedes_version_1_and_keeps_its_figures(
    client, workspace, entity, validated, act
):
    v1 = validated()
    v1_facts = v1["facts"]
    v2 = act(v1, "restatements", {"reason": "Revenue restated"}).json()
    client.patch(
        f"/api/v1/workspaces/{workspace.public_id}/statements/{v2['id']}/",
        {"line_items": [row("revenue", "1300"), row("net_income", "125")]},
        format="json",
    )

    # Until version 2 is validated, analyses keep using version 1.
    assert assemble_analysis_input(entity=entity, period=FY).facts.get(LineItem.REVENUE) == Decimal(
        "12505000000"
    )

    response = act(v2, "validate")

    assert response.status_code == 200
    assert response.json()["version"] == 2
    v1_now = get_statement(client, workspace, v1).json()
    assert v1_now["status"] == "superseded"
    assert v1_now["facts"] == v1_facts  # version 1 keeps its figures
    assembled = assemble_analysis_input(entity=entity, period=FY)
    assert assembled.facts.get(LineItem.REVENUE) == Decimal("13000000000")
    assert [s.version for s in assembled.statements] == [2]


def test_version_3_restates_version_2(validated, act):
    v1 = validated()
    v2 = act(v1, "restatements", {"reason": "First correction"}).json()
    act(v2, "validate")

    v3 = act(v2, "restatements", {"reason": "Second correction"}).json()
    act(v3, "validate")

    statuses = dict(FinancialStatement.objects.values_list("version", "status"))
    assert statuses == {1: SUPERSEDED, 2: SUPERSEDED, 3: VALIDATED}


def test_a_superseded_version_cannot_be_restated_again(validated, act):
    v1 = validated()
    act(act(v1, "restatements", {"reason": "Correction"}).json(), "validate")

    assert act(v1, "restatements", {"reason": "Again"}).status_code == 409


# --- Roles, isolation and query budget ----------------------------------------------------


@pytest.mark.parametrize("action", ["validate", "restatements"])
@pytest.mark.parametrize("role", [None, WorkspaceRole.VIEWER])
def test_viewers_and_outsiders_cannot_act(
    api_client, workspace, entity, make_statement, add_to_workspace, make_user, action, role
):
    statement = make_statement(entity=entity, status=DRAFT if action == "validate" else VALIDATED)
    api_client.force_login(make_user() if role is None else add_to_workspace(workspace, role))

    response = api_client.post(
        f"/api/v1/workspaces/{workspace.public_id}/statements/{statement.public_id}/{action}/",
        {"reason": "x"},
        format="json",
    )

    assert response.status_code == (404 if role is None else 403)
    statement.refresh_from_db()
    assert statement.status == (DRAFT if action == "validate" else VALIDATED)


@pytest.mark.parametrize("action", ["validate", "restatements"])
def test_another_workspaces_statement_is_not_found(client, workspace, make_statement, action):
    foreign = make_statement(status=DRAFT if action == "validate" else VALIDATED)

    response = client.post(
        f"/api/v1/workspaces/{workspace.public_id}/statements/{foreign.public_id}/{action}/",
        {"reason": "x"},
        format="json",
    )

    assert response.status_code == 404
    assert FinancialStatement.objects.count() == 1


@pytest.mark.parametrize("action", ["validate", "restatements"])
def test_anonymous_callers_get_401(api_client, workspace, entity, make_statement, action):
    statement = make_statement(entity=entity)

    response = api_client.post(
        f"/api/v1/workspaces/{workspace.public_id}/statements/{statement.public_id}/{action}/"
    )

    assert response.status_code == 401


def test_a_validated_statement_with_rows_and_facts_costs_four_queries(
    client, workspace, validated, assert_app_queries
):
    statement = validated()

    with assert_app_queries(4):  # access + statement + rows + facts (rows joined)
        response = get_statement(client, workspace, statement)

    assert len(response.json()["facts"]) == 2
