"""Entity, draft statement and taxonomy endpoints (MVP step 3a)."""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from apps.audit.models import AuditEvent
from apps.documents.models import SourceDocumentKind
from apps.financial_records.models import FinancialStatement, StatementStatus
from apps.workspaces.models import WorkspaceRole
from domain.financial_statements import LineItem

pytestmark = pytest.mark.django_db

VIEWER, EDITOR, OWNER = WorkspaceRole.VIEWER, WorkspaceRole.EDITOR, WorkspaceRole.OWNER


def entities_url(ws):
    return f"/api/v1/workspaces/{ws.public_id}/entities/"


def entity_url(ws, entity):
    return f"/api/v1/workspaces/{ws.public_id}/entities/{entity.public_id}/"


def statements_url(ws, entity):
    return f"/api/v1/workspaces/{ws.public_id}/entities/{entity.public_id}/statements/"


def statement_url(ws, statement):
    return f"/api/v1/workspaces/{ws.public_id}/statements/{statement.public_id}/"


@pytest.fixture
def as_user(api_client):
    def sign_in(user):
        api_client.force_login(user)
        return api_client

    return sign_in


@pytest.fixture
def workspace(make_workspace):
    return make_workspace()


@pytest.fixture
def editor(workspace, add_to_workspace):
    return add_to_workspace(workspace, EDITOR)


@pytest.fixture
def entity(workspace, make_entity):
    return make_entity(workspace=workspace, name="Example Lending Co")


def income_statement(**overrides):
    body = {
        "statement_type": "income_statement",
        "period_start": "2025-04-01",
        "period_end": "2026-03-31",
        "period_type": "annual",
        "currency": "INR",
        "reported_scale": "crores",
        "line_items": [
            {"label": "Revenue from operations", "line_item_code": "revenue", "amount": "1250.50"},
            {"label": "Cost of materials", "line_item_code": "cost_of_revenue", "amount": "700.25"},
        ],
    }
    return {**body, **overrides}


def rows(*amounts, code="revenue"):
    return [{"label": "Row", "line_item_code": code, "amount": amount} for amount in amounts]


# --- Roles and isolation ----------------------------------------------------------------

# (method, url builder, body, minimum role, success status)
ENDPOINTS = [
    ("get", lambda ws, e, s: entities_url(ws), None, VIEWER, 200),
    (
        "post",
        lambda ws, e, s: entities_url(ws),
        {"name": "New Co", "entity_type": "business"},
        EDITOR,
        201,
    ),
    ("get", lambda ws, e, s: entity_url(ws, e), None, VIEWER, 200),
    ("get", lambda ws, e, s: statements_url(ws, e), None, VIEWER, 200),
    ("post", lambda ws, e, s: statements_url(ws, e), "new-statement", EDITOR, 201),
    ("get", lambda ws, e, s: statement_url(ws, s), None, VIEWER, 200),
    ("patch", lambda ws, e, s: statement_url(ws, s), {"currency": "USD"}, EDITOR, 200),
]
ROLES = [VIEWER, EDITOR, OWNER]


@pytest.fixture
def draft(entity, make_statement, make_line_item):
    statement = make_statement(entity=entity, status=StatementStatus.DRAFT)
    make_line_item(statement, "revenue", "10")
    return statement


@pytest.mark.parametrize(("method", "url", "body", "minimum", "ok"), ENDPOINTS)
@pytest.mark.parametrize("role", [None, *ROLES])
def test_role_matrix(
    workspace,
    entity,
    draft,
    add_to_workspace,
    make_user,
    as_user,
    method,
    url,
    body,
    minimum,
    ok,
    role,
):
    caller = make_user() if role is None else add_to_workspace(workspace, role)
    if body == "new-statement":
        body = income_statement(period_start="2024-04-01", period_end="2025-03-31")

    response = getattr(as_user(caller), method)(url(workspace, entity, draft), body, format="json")

    if role is None:
        expected = 404
    elif ROLES.index(role) >= ROLES.index(minimum):
        expected = ok
    else:
        expected = 403
    assert response.status_code == expected, response.json()


@pytest.mark.parametrize(("method", "url", "body", "minimum", "ok"), ENDPOINTS)
def test_anonymous_callers_get_401(
    api_client, workspace, entity, draft, method, url, body, minimum, ok
):
    response = getattr(api_client, method)(url(workspace, entity, draft), {}, format="json")

    assert response.status_code == 401


@pytest.mark.parametrize("target", ["entity", "entity statements", "statement", "statement edit"])
def test_another_workspaces_entity_or_statement_is_not_found_from_mine(
    workspace, editor, make_entity, make_statement, as_user, target
):
    foreign_entity = make_entity()  # in its own workspace
    foreign_statement = make_statement(entity=foreign_entity, status=StatementStatus.DRAFT)
    client = as_user(editor)

    response = {
        "entity": lambda: client.get(entity_url(workspace, foreign_entity)),
        "entity statements": lambda: client.post(
            statements_url(workspace, foreign_entity), income_statement(), format="json"
        ),
        "statement": lambda: client.get(statement_url(workspace, foreign_statement)),
        "statement edit": lambda: client.patch(
            statement_url(workspace, foreign_statement), {"currency": "EUR"}, format="json"
        ),
    }[target]()

    assert response.status_code == 404
    assert FinancialStatement.objects.filter(entity=foreign_entity).count() == 1
    assert FinancialStatement.objects.get(pk=foreign_statement.pk).currency == "USD"


# --- Entities ---------------------------------------------------------------------------


def test_editors_create_entities(workspace, editor, as_user):
    response = as_user(editor).post(
        entities_url(workspace),
        {
            "name": "Example Lending Co",
            "entity_type": "business",
            "default_currency": "INR",
            "fiscal_year_end_month": 3,
        },
        format="json",
    )

    assert response.status_code == 201
    body = response.json()
    assert (body["name"], body["default_currency"], body["fiscal_year_end_month"]) == (
        "Example Lending Co",
        "INR",
        3,
    )
    assert AuditEvent.objects.filter(action="entity.created").exists()


def test_entity_currency_and_fiscal_month_are_optional(workspace, editor, as_user):
    response = as_user(editor).post(
        entities_url(workspace), {"name": "Solo", "entity_type": "individual"}, format="json"
    )

    assert response.status_code == 201
    assert (response.json()["default_currency"], response.json()["fiscal_year_end_month"]) == (
        None,
        None,
    )


def test_a_duplicate_entity_name_is_a_conflict(workspace, entity, editor, as_user):
    response = as_user(editor).post(
        entities_url(workspace), {"name": entity.name, "entity_type": "business"}, format="json"
    )

    assert response.status_code == 409


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"name": "X", "entity_type": "partnership"}, "entity_type"),
        ({"name": "X", "entity_type": "business", "default_currency": "inr"}, "default_currency"),
        (
            {"name": "X", "entity_type": "business", "fiscal_year_end_month": 13},
            "fiscal_year_end_month",
        ),
    ],
)
def test_invalid_entities_are_rejected_field_by_field(workspace, editor, as_user, body, field):
    response = as_user(editor).post(entities_url(workspace), body, format="json")

    assert response.status_code == 400
    assert field in response.json()["error"]["details"]


def test_entity_list_shows_this_workspace_only_in_three_queries(
    workspace, entity, editor, make_entity, as_user, assert_app_queries
):
    make_entity()  # another workspace
    client = as_user(editor)

    with assert_app_queries(3):  # access + count + page
        response = client.get(entities_url(workspace))

    assert [item["id"] for item in response.json()["results"]] == [str(entity.public_id)]


# --- Creating draft statements ----------------------------------------------------------


def test_editors_create_a_draft_with_its_raw_rows(workspace, entity, editor, as_user):
    response = as_user(editor).post(
        statements_url(workspace, entity),
        income_statement(
            line_items=[
                {
                    "label": "Revenue from operations",
                    "line_item_code": "revenue",
                    "amount": "1250.50",
                },
                {"label": "Memo: rounding", "amount": "0.01", "source_reference": "note 4"},
                {"label": "Other income", "line_item_code": "", "amount": None},
            ]
        ),
        format="json",
    )

    assert response.status_code == 201
    body = response.json()
    assert (body["status"], body["version"], body["supersedes_id"]) == ("draft", 1, None)
    assert (body["currency"], body["reported_scale"]) == ("INR", "crores")
    assert body["line_items"] == [
        {
            "id": body["line_items"][0]["id"],
            "row_number": 1,
            "label": "Revenue from operations",
            "line_item_code": "revenue",
            "amount": "1250.500000",
            "raw_value": "1250.50",
            "source_reference": None,
        },
        {
            "id": body["line_items"][1]["id"],
            "row_number": 2,
            "label": "Memo: rounding",
            "line_item_code": None,
            "amount": "0.010000",
            "raw_value": "0.01",
            "source_reference": "note 4",
        },
        {
            "id": body["line_items"][2]["id"],
            "row_number": 3,
            "label": "Other income",
            "line_item_code": None,
            "amount": None,  # a blank cell stays unknown, never zero
            "raw_value": "",
            "source_reference": None,
        },
    ]
    statement = FinancialStatement.objects.get(public_id=body["id"])
    assert statement.source_document.kind == SourceDocumentKind.MANUAL_ENTRY
    assert statement.source_document.created_by == editor
    assert not statement.facts.exists()  # facts are created when the draft is validated (3b)
    assert AuditEvent.objects.filter(
        action="statement.created", target_public_id=statement.public_id
    ).exists()


def test_all_three_statements_can_be_entered_for_one_period(workspace, entity, editor, as_user):
    # MVP acceptance criterion 3: FY2025 in INR crores, by hand.
    client = as_user(editor)
    bodies = [
        income_statement(),
        income_statement(
            statement_type="balance_sheet",
            line_items=rows("5000", code="total_assets") + rows("2000", code="total_equity"),
        ),
        income_statement(
            statement_type="cash_flow",
            line_items=rows("-120.5", code="capital_expenditure"),
        ),
    ]

    statuses = [
        client.post(statements_url(workspace, entity), b, format="json").status_code for b in bodies
    ]

    assert statuses == [201, 201, 201]
    listed = client.get(statements_url(workspace, entity)).json()
    assert sorted(item["statement_type"] for item in listed["results"]) == [
        "balance_sheet",
        "cash_flow",
        "income_statement",
    ]


@pytest.mark.parametrize(
    ("amount", "message"),
    [
        (1250.5, "decimal strings"),
        (1250, "decimal strings"),
        ("12.3456789", "6 decimal places"),
        ("NaN", "valid number"),
        ("Infinity", "valid number"),
        ("12,50", "valid number"),
        ("1E+24", "smaller than 10^24"),
        ("1" * 65, "64 characters"),
    ],
)
def test_amounts_must_be_exact_decimal_strings(workspace, entity, editor, as_user, amount, message):
    response = as_user(editor).post(
        statements_url(workspace, entity), income_statement(line_items=rows(amount)), format="json"
    )

    assert response.status_code == 400
    [error] = response.json()["error"]["details"]["line_items"]["0"]["amount"]
    assert message in error


@pytest.mark.parametrize("amount", ["1e3", "-0.000001", "  42  ", "1.500000000"])
def test_any_exact_decimal_string_is_accepted(workspace, entity, editor, as_user, amount):
    response = as_user(editor).post(
        statements_url(workspace, entity), income_statement(line_items=rows(amount)), format="json"
    )

    assert response.status_code == 201
    assert response.json()["line_items"][0]["raw_value"] == amount


def test_an_amount_too_large_once_scaled_is_rejected(workspace, entity, editor, as_user):
    # 10^17 crores is 10^24 units: too large for numeric(30,6) (FA-15).
    response = as_user(editor).post(
        statements_url(workspace, entity),
        income_statement(line_items=rows("99999999999999999", "100000000000000000")),
        format="json",
    )

    errors = response.json()["error"]["details"]["line_items"]
    assert response.status_code == 400
    assert list(errors) == ["1"]
    assert "Too large once scaled from crores" in errors["1"]["amount"][0]


def test_a_code_is_allowed_only_on_its_own_statement_and_only_once(
    workspace, entity, editor, as_user
):
    response = as_user(editor).post(
        statements_url(workspace, entity),
        income_statement(
            line_items=[
                {"label": "Sales", "line_item_code": "revenue", "amount": "1"},
                {"label": "Assets", "line_item_code": "total_assets", "amount": "1"},
                {"label": "Sales again", "line_item_code": "revenue", "amount": "1"},
            ]
        ),
        format="json",
    )

    errors = response.json()["error"]["details"]["line_items"]
    assert response.status_code == 400
    assert errors["1"]["line_item_code"] == [
        "total_assets belongs on the balance_sheet, not the income_statement."
    ]
    assert errors["2"]["line_item_code"] == ["revenue is already on row 1."]


@pytest.mark.parametrize(
    ("override", "field"),
    [
        ({"currency": "inr"}, "currency"),
        ({"currency": "RUPEES"}, "currency"),
        ({"period_start": "2026-04-01"}, "period_end"),
        ({"reported_scale": "hundreds"}, "reported_scale"),
        ({"statement_type": "equity_statement"}, "statement_type"),
        ({"line_items": [{"label": "x", "line_item_code": "ebitda", "amount": "1"}]}, "line_items"),
        ({"line_items": [{"label": "x", "amount": "1"}] * 501}, "line_items"),
    ],
    ids=[
        "lowercase currency",
        "long currency",
        "period order",
        "scale",
        "type",
        "unknown code",
        "too many rows",
    ],
)
def test_invalid_statements_are_rejected_field_by_field(
    workspace, entity, editor, as_user, override, field
):
    response = as_user(editor).post(
        statements_url(workspace, entity), income_statement(**override), format="json"
    )

    assert response.status_code == 400
    assert field in response.json()["error"]["details"]
    assert not FinancialStatement.objects.exists()


@pytest.mark.parametrize("existing", [StatementStatus.DRAFT, StatementStatus.VALIDATED])
def test_a_second_statement_for_the_same_period_is_a_conflict(
    workspace, entity, editor, make_statement, as_user, existing
):
    make_statement(
        entity=entity,
        status=existing,
        period_start=date(2025, 4, 1),
        period_end=date(2026, 3, 31),
    )

    response = as_user(editor).post(
        statements_url(workspace, entity), income_statement(), format="json"
    )

    assert response.status_code == 409
    assert "restate the validated version" in response.json()["error"]["message"]


def test_listing_statements_costs_four_queries(
    workspace, entity, editor, make_statement, restate, as_user, assert_app_queries
):
    v1 = make_statement(entity=entity, status=StatementStatus.VALIDATED)
    restate(v1)
    make_statement(entity=entity, statement_type="balance_sheet")
    client = as_user(editor)

    with assert_app_queries(4):  # access + entity + count + page (entity and supersedes joined)
        response = client.get(statements_url(workspace, entity))

    results = response.json()["results"]
    assert [(r["statement_type"], r["version"]) for r in results] == [
        ("balance_sheet", 1),
        ("income_statement", 2),
        ("income_statement", 1),
    ]
    assert results[1]["supersedes_id"] == str(v1.public_id)


# --- Reading and editing a statement ----------------------------------------------------


def test_a_statement_with_its_rows_costs_three_queries(
    workspace, draft, editor, as_user, assert_app_queries
):
    client = as_user(editor)

    with assert_app_queries(3):  # access + statement (entity, supersedes joined) + rows
        response = client.get(statement_url(workspace, draft))

    assert [row["line_item_code"] for row in response.json()["line_items"]] == ["revenue"]


def test_editing_header_fields_keeps_the_rows(workspace, draft, editor, as_user):
    response = as_user(editor).patch(
        statement_url(workspace, draft), {"currency": "EUR", "period_type": "other"}, format="json"
    )

    assert response.status_code == 200
    assert (response.json()["currency"], response.json()["period_type"]) == ("EUR", "other")
    assert [row["amount"] for row in response.json()["line_items"]] == ["10.000000"]
    assert AuditEvent.objects.filter(
        action="statement.updated", metadata__rows_replaced=False
    ).exists()


def test_sending_line_items_replaces_all_rows(workspace, draft, editor, as_user):
    response = as_user(editor).patch(
        statement_url(workspace, draft),
        {"line_items": rows("5") + rows("3", code="cost_of_revenue")},
        format="json",
    )

    assert response.status_code == 200
    assert [
        (r["row_number"], r["line_item_code"], r["raw_value"])
        for r in response.json()["line_items"]
    ] == [
        (1, "revenue", "5"),
        (2, "cost_of_revenue", "3"),
    ]
    assert draft.line_items.count() == 2


def test_rows_sent_in_an_edit_are_complete_rows(workspace, draft, editor, as_user):
    response = as_user(editor).patch(
        statement_url(workspace, draft),
        {"line_items": [{"line_item_code": "revenue", "amount": "5"}]},  # no label
        format="json",
    )

    assert response.status_code == 400
    assert "label" in response.json()["error"]["details"]["line_items"]["0"]
    assert [row.raw_value for row in draft.line_items.all()] == ["10"]


@pytest.mark.parametrize(
    "field", [{"statement_type": "balance_sheet"}, {"reported_scale": "lakhs"}]
)
def test_changing_type_or_scale_needs_the_rows_again(workspace, draft, editor, as_user, field):
    response = as_user(editor).patch(statement_url(workspace, draft), field, format="json")

    assert response.status_code == 400
    assert "line_items" in response.json()["error"]["details"]


def test_edited_rows_are_checked_against_the_statement_type_and_scale(
    workspace, draft, editor, as_user
):
    # The draft is an income statement in thousands (the builder's defaults).
    response = as_user(editor).patch(
        statement_url(workspace, draft),
        {"line_items": rows("1", code="total_assets") + rows("1E+21", code="net_income")},
        format="json",
    )

    errors = response.json()["error"]["details"]["line_items"]
    assert response.status_code == 400
    assert "belongs on the balance_sheet" in errors["0"]["line_item_code"][0]
    assert "Too large once scaled from thousands" in errors["1"]["amount"][0]


@pytest.mark.parametrize("status", [StatementStatus.VALIDATED, StatementStatus.SUPERSEDED])
def test_only_a_draft_can_be_edited(workspace, entity, editor, make_statement, as_user, status):
    statement = make_statement(entity=entity, status=status)

    response = as_user(editor).patch(
        statement_url(workspace, statement), {"currency": "EUR"}, format="json"
    )

    assert response.status_code == 409
    statement.refresh_from_db()
    assert statement.currency == "USD"


@pytest.mark.parametrize(
    "change",
    [{"period_start": "2025-02-01"}, {"period_end": "2025-11-30"}],
)
def test_a_restatement_draft_keeps_its_period(
    workspace, entity, editor, make_statement, restate, as_user, change
):
    draft = restate(make_statement(entity=entity, status=StatementStatus.VALIDATED))

    response = as_user(editor).patch(statement_url(workspace, draft), change, format="json")

    assert response.status_code == 409
    assert "keeps the statement type and period" in response.json()["error"]["message"]


def test_moving_a_draft_onto_an_existing_statement_is_a_conflict(
    workspace, entity, editor, make_statement, as_user
):
    make_statement(
        entity=entity, **{"period_start": date(2024, 1, 1), "period_end": date(2024, 12, 31)}
    )
    draft = make_statement(entity=entity, status=StatementStatus.DRAFT)

    response = as_user(editor).patch(
        statement_url(workspace, draft),
        {"period_start": "2024-01-01", "period_end": "2024-12-31"},
        format="json",
    )

    assert response.status_code == 409
    draft.refresh_from_db()
    assert draft.period_start == date(2025, 1, 1)


def test_a_draft_can_be_moved_to_a_free_period(workspace, draft, editor, as_user):
    response = as_user(editor).patch(
        statement_url(workspace, draft),
        {"period_start": "2024-01-01", "period_end": "2024-12-31"},
        format="json",
    )

    assert response.status_code == 200
    assert response.json()["period_end"] == "2024-12-31"


# --- Taxonomy ----------------------------------------------------------------------------


def test_the_taxonomy_lists_every_line_item_with_its_definition(api_client, make_user):
    api_client.force_login(make_user())

    response = api_client.get("/api/v1/line-items/")

    body = response.json()
    assert response.status_code == 200
    assert body["count"] == len(LineItem) == len(body["results"])
    debt = next(item for item in body["results"] if item["code"] == "total_debt")
    assert debt == {
        "code": "total_debt",
        "statement_type": "balance_sheet",
        "label": "Total debt",
        "definition": LineItem.TOTAL_DEBT.definition,
        "sign": "non_negative",
    }
    signs = {item["code"]: item["sign"] for item in body["results"]}
    assert (signs["capital_expenditure"], signs["net_income"]) == ("non_positive", "signed")


def test_the_taxonomy_needs_a_signed_in_user(api_client):
    assert api_client.get("/api/v1/line-items/").status_code == 401


def test_unknown_ids_are_not_found(workspace, editor, as_user):
    client = as_user(editor)
    missing = uuid.uuid4()

    assert (
        client.get(f"/api/v1/workspaces/{workspace.public_id}/entities/{missing}/").status_code
        == 404
    )
    assert (
        client.get(f"/api/v1/workspaces/{workspace.public_id}/statements/{missing}/").status_code
        == 404
    )
