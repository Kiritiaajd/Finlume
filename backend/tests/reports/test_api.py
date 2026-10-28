"""Saved reports over analysis runs (MVP step 5b)."""

from __future__ import annotations

import uuid

import pytest

from apps.audit.models import AuditEvent
from apps.reports.models import Report
from apps.workspaces.models import WorkspaceRole
from services.statement_analysis import restate_statement, run_analysis, validate_statement
from tests.analysis.conftest import FY2025

pytestmark = pytest.mark.django_db


@pytest.fixture
def client(api_client, owner):
    api_client.force_login(owner)
    return api_client


def reports_url(workspace):
    return f"/api/v1/workspaces/{workspace.public_id}/reports/"


def report_url(workspace, report_id):
    return f"/api/v1/workspaces/{workspace.public_id}/reports/{report_id}/"


@pytest.fixture
def create(client, workspace):
    def post(body):
        return client.post(reports_url(workspace), body, format="json")

    return post


# --- Creating and reading ------------------------------------------------------------------


def test_a_report_shows_its_runs_in_order_rendered_from_their_results(create, make_run):
    first, second = make_run(), make_run()

    response = create(
        {
            "title": "FY2025 credit review",
            "notes": "Margins look stable; check the debt covenant.",
            "run_ids": [str(second.public_id), str(first.public_id)],
        }
    )

    body = response.json()
    assert response.status_code == 201, body
    assert (body["title"], body["notes"]) == (
        "FY2025 credit review",
        "Margins look stable; check the debt covenant.",
    )
    assert [run["id"] for run in body["runs"]] == [str(second.public_id), str(first.public_id)]
    run = body["runs"][0]
    assert run["engine_version"] == second.engine_version
    assert run["input_fingerprint"] == second.input_fingerprint
    assert run["uses_superseded_statement"] is False
    assert [(m["code"], m["value"]) for m in run["metrics"]][:2] == [
        ("gross_margin", "0.400000"),
        ("operating_margin", "0.150000"),
    ]
    assert len(run["metrics"]) == 7
    assert AuditEvent.objects.filter(action="report.created", metadata={"runs": 2}).exists()


def test_a_report_may_start_empty(create):
    response = create({"title": "Draft review"})

    assert response.status_code == 201
    assert (response.json()["notes"], response.json()["runs"]) == ("", [])


def test_a_report_follows_its_runs_and_never_copies_figures(
    client, workspace, owner, entity, create, make_run
):
    run = make_run()
    report_id = create({"title": "Review", "run_ids": [str(run.public_id)]}).json()["id"]
    income = entity.statements.get(statement_type="income_statement")
    draft = restate_statement(actor=owner, workspace=workspace, statement=income, reason="Fix")
    validate_statement(actor=owner, workspace=workspace, statement=draft)

    reloaded = client.get(report_url(workspace, report_id)).json()

    [shown] = reloaded["runs"]
    assert shown["uses_superseded_statement"] is True  # the report says the inputs changed
    assert shown["metrics"][0]["value"] == "0.400000"  # and still shows the run's own figures


def test_listing_reports_shows_this_workspace_only(
    client, workspace, create, make_run, make_workspace
):
    create({"title": "Older", "run_ids": [str(make_run().public_id)]})
    create({"title": "Newer"})
    Report.objects.create(workspace=make_workspace(), title="Someone else's")

    body = client.get(reports_url(workspace)).json()

    assert [(r["title"], r["run_count"]) for r in body["results"]] == [("Newer", 0), ("Older", 1)]


# --- Editing -----------------------------------------------------------------------------


def test_editors_change_the_title_notes_and_runs(client, workspace, create, make_run):
    first, third = make_run(), make_run()
    report_id = create({"title": "Review", "run_ids": [str(first.public_id)]}).json()["id"]

    response = client.patch(
        report_url(workspace, report_id),
        {"notes": "Added two runs.", "run_ids": [str(third.public_id), str(first.public_id)]},
        format="json",
    )

    body = response.json()
    assert response.status_code == 200
    assert (body["title"], body["notes"]) == ("Review", "Added two runs.")  # title kept
    assert [run["id"] for run in body["runs"]] == [str(third.public_id), str(first.public_id)]
    assert AuditEvent.objects.filter(
        action="report.updated", metadata={"fields": ["notes", "runs"]}
    ).exists()


def test_reordering_runs_keeps_every_run_once(client, workspace, create, make_run):
    runs = [str(make_run().public_id) for _ in range(3)]
    report_id = create({"title": "Review", "run_ids": runs}).json()["id"]

    response = client.patch(
        report_url(workspace, report_id), {"run_ids": runs[::-1]}, format="json"
    )

    assert [run["id"] for run in response.json()["runs"]] == runs[::-1]


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"title": ""}, "title"),
        ({"title": "x" * 201}, "title"),
        ({"title": "Review", "run_ids": ["not-a-uuid"]}, "run_ids"),
        ({"title": "Review", "notes": "x" * 10_001}, "notes"),
    ],
)
def test_invalid_reports_are_rejected(create, body, field):
    response = create(body)

    assert response.status_code == 400
    assert field in response.json()["error"]["details"]
    assert not Report.objects.exists()


def test_a_run_appears_once_per_report(create, make_run):
    run_id = str(make_run().public_id)

    response = create({"title": "Review", "run_ids": [run_id, run_id]})

    assert response.status_code == 400
    assert "only once" in response.json()["error"]["details"]["run_ids"][0]


def test_runs_from_another_workspace_or_unknown_are_not_found(
    create, make_workspace, make_entity, make_statement, make_line_item
):
    elsewhere = make_workspace()
    foreign_owner = elsewhere.memberships.get().user
    foreign_entity = make_entity(workspace=elsewhere)
    draft = make_statement(entity=foreign_entity, status="draft")
    make_line_item(draft, "revenue", "1")
    validate_statement(actor=foreign_owner, workspace=elsewhere, statement=draft)
    foreign_run = run_analysis(
        actor=foreign_owner, workspace=elsewhere, entity=foreign_entity, period=FY2025
    )
    unknown = uuid.uuid4()

    response = create({"title": "Review", "run_ids": [str(foreign_run.public_id), str(unknown)]})

    assert response.status_code == 400
    assert response.json()["error"]["details"]["run_ids"] == [
        f"No run {foreign_run.public_id} in this workspace.",
        f"No run {unknown} in this workspace.",
    ]
    assert not Report.objects.exists()


def test_a_report_has_at_most_fifty_runs(create):
    response = create({"title": "Review", "run_ids": [str(uuid.uuid4()) for _ in range(51)]})

    assert response.status_code == 400
    assert "at most 50" in response.json()["error"]["details"]["run_ids"][0]


# --- Access and query budgets ------------------------------------------------------------


@pytest.mark.parametrize(
    ("role", "read", "write"),
    [(None, 404, 404), (WorkspaceRole.VIEWER, 200, 403), (WorkspaceRole.EDITOR, 200, 200)],
)
def test_viewers_read_and_editors_write(
    api_client, workspace, create, add_to_workspace, make_user, role, read, write
):
    report_id = create({"title": "Review"}).json()["id"]
    api_client.force_login(make_user() if role is None else add_to_workspace(workspace, role))

    assert api_client.get(reports_url(workspace)).status_code == read
    assert api_client.get(report_url(workspace, report_id)).status_code == read
    patched = api_client.patch(report_url(workspace, report_id), {"title": "New"}, format="json")
    assert patched.status_code == write
    created = api_client.post(reports_url(workspace), {"title": "Mine"}, format="json")
    assert created.status_code == (201 if write == 200 else write)


def test_anonymous_callers_get_401(api_client, workspace):
    assert api_client.get(reports_url(workspace)).status_code == 401
    assert api_client.post(reports_url(workspace), {"title": "x"}, format="json").status_code == 401


def test_another_workspaces_report_is_not_found(client, workspace, make_workspace):
    foreign = Report.objects.create(workspace=make_workspace(), title="Someone else's")

    assert client.get(report_url(workspace, foreign.public_id)).status_code == 404
    response = client.patch(
        report_url(workspace, foreign.public_id), {"title": "Mine"}, format="json"
    )
    assert response.status_code == 404
    foreign.refresh_from_db()
    assert foreign.title == "Someone else's"


def test_listing_reports_costs_three_queries(client, workspace, create, assert_app_queries):
    create({"title": "One"})
    create({"title": "Two"})

    with assert_app_queries(3):  # access + count + page (run counts joined)
        response = client.get(reports_url(workspace))

    assert response.json()["count"] == 2


def test_a_report_costs_five_queries_whatever_its_size(
    client, workspace, create, make_run, assert_app_queries
):
    report_id = create(
        {"title": "Review", "run_ids": [str(make_run().public_id) for _ in range(3)]}
    ).json()["id"]

    with assert_app_queries(5):  # access + report + runs + metrics + issues
        response = client.get(report_url(workspace, report_id))

    assert len(response.json()["runs"]) == 3
