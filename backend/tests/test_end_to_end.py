"""The MVP acceptance criteria 1 to 10, through the API only (MVP step 6).

Real registration and sign-in with CSRF enforced, as a browser would. Every
response, errors included, is checked against the committed OpenAPI contract.
Fictional data only.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from domain.calculations import ENGINE_VERSION

from .api.contract import assert_matches_contract

pytestmark = pytest.mark.django_db

PASSWORD = "correct-horse-battery-9"
FY2025 = {"period_start": "2025-04-01", "period_end": "2026-03-31", "period_type": "annual"}
FY2024 = {"period_start": "2024-04-01", "period_end": "2025-03-31", "period_type": "annual"}


class Browser:
    """One person's session: CSRF-checked writes, contract-checked responses."""

    def __init__(self) -> None:
        self.client = APIClient(enforce_csrf_checks=True)
        self.call("get", "/api/v1/auth/csrf/", status=204)

    def call(
        self, method: str, path: str, body: Any = None, *, status: int, multipart: bool = False
    ) -> Any:
        headers = {}
        if method != "get":
            headers["X-CSRFToken"] = self.client.cookies["csrftoken"].value
        response = getattr(self.client, method)(
            path, body, format="multipart" if multipart else "json", headers=headers
        )
        assert response.status_code == status, (method, path, response.content[:500])
        assert_matches_contract(response, method, path)
        return response.json() if response.content else None


def register(email: str) -> tuple[Browser, dict[str, Any]]:
    browser = Browser()
    me = browser.call(
        "post", "/api/v1/auth/register/", {"email": email, "password": PASSWORD}, status=201
    )
    return browser, me


def rows(**amounts: str) -> list[dict[str, str]]:
    return [{"label": code, "line_item_code": code, "amount": a} for code, a in amounts.items()]


def test_the_mvp_acceptance_criteria_through_the_api():
    # 1. A new user registers, signs in and finds their personal workspace.
    alice, me = register("alice@example.com")
    alice.call("post", "/api/v1/auth/logout/", status=204)
    alice.call("get", "/api/v1/me/", status=401)
    alice.call("get", "/api/v1/auth/csrf/", status=204)
    alice.call(
        "post",
        "/api/v1/auth/login/",
        {"email": "ALICE@example.com", "password": PASSWORD},
        status=200,
    )
    personal = alice.call("get", f"/api/v1/workspaces/{me['personal_workspace_id']}/", status=200)
    assert (personal["kind"], personal["my_role"]) == ("personal", "owner")

    # 2. Organization, members and an organization workspace; viewers read but do not
    #    edit; organization members outside the workspace, even admins, get 404.
    bob, bob_me = register("bob@example.com")
    carol, carol_me = register("carol@example.com")
    org = alice.call("post", "/api/v1/organizations/", {"name": "Example Lending"}, status=201)
    for email in ("bob@example.com", "carol@example.com"):
        alice.call(
            "post",
            f"/api/v1/organizations/{org['id']}/members/",
            {"email": email, "role": "member"},
            status=201,
        )
    ws = alice.call(
        "post",
        "/api/v1/workspaces/",
        {"organization_id": org["id"], "name": "Borrower review"},
        status=201,
    )
    W = f"/api/v1/workspaces/{ws['id']}"
    alice.call("post", f"{W}/members/", {"user_id": bob_me["id"], "role": "viewer"}, status=201)
    assert bob.call("get", f"{W}/", status=200)["my_role"] == "viewer"
    bob.call("patch", f"{W}/", {"name": "Mine now"}, status=403)
    carol.call("get", f"{W}/", status=404)
    alice.call(
        "patch",
        f"/api/v1/organizations/{org['id']}/members/{carol_me['id']}/",
        {"role": "admin"},
        status=200,
    )
    carol.call("get", f"{W}/", status=404)  # an organization admin is still not a member

    # 3. A reporting entity, and all three FY2025 statements in INR crores, by hand.
    entity = alice.call(
        "post",
        f"{W}/entities/",
        {"name": "Example Trading Co", "entity_type": "business"},
        status=201,
    )
    E = f"{W}/entities/{entity['id']}"
    statements = {}
    for statement_type, figures in {
        "income_statement": rows(
            revenue="1000",
            cost_of_revenue="600",
            gross_profit="400",
            operating_income="150",
            net_income="100",
        ),
        "balance_sheet": rows(  # no total_debt: debt to equity is not computable
            total_current_assets="500",
            total_current_liabilities="250",
            total_assets="1200",
            total_liabilities="700",
            total_equity="500",
        ),
        "cash_flow": rows(net_cash_from_operating_activities="120", capital_expenditure="-40"),
    }.items():
        draft = alice.call(
            "post",
            f"{E}/statements/",
            {
                **FY2025,
                "statement_type": statement_type,
                "currency": "INR",
                "reported_scale": "crores",
                "line_items": figures,
            },
            status=201,
        )
        validated = alice.call("post", f"{W}/statements/{draft['id']}/validate/", status=200)
        assert validated["issues"] == []
        statements[statement_type] = validated
    assert statements["income_statement"]["facts"][0] == {
        "line_item": "revenue",
        "value": "10000000000.000000",  # 1,000 crores in base units
        "row_id": statements["income_statement"]["line_items"][0]["id"],
        "review_status": "confirmed",
    }

    # 6. All seven ratios with methodology and inputs; a missing input is not
    #    computable, never zero.
    first_run = alice.call("post", f"{E}/analyses/", FY2025, status=201)
    metrics = {m["code"]: m for m in first_run["metrics"]}
    assert len(metrics) == 7
    assert metrics["gross_margin"]["value"] == "0.400000"
    assert metrics["return_on_equity"]["inputs"] == {
        "net_income": "1000000000.000000",
        "total_equity": "5000000000.000000",
    }
    assert all(m["methodology"] for m in metrics.values())
    assert metrics["debt_to_equity"]["value"] is None
    assert [i["code"] for i in metrics["debt_to_equity"]["issues"]] == ["missing_input"]

    # 7. The saved run shows its engine version, reloads identically, and a re-run on
    #    unchanged inputs gives the same fingerprint and values.
    assert first_run["engine_version"] == ENGINE_VERSION == "0.1.0"
    R = f"{W}/analyses"
    assert alice.call("get", f"{R}/{first_run['id']}/", status=200) == first_run
    rerun = alice.call("post", f"{E}/analyses/", FY2025, status=201)
    assert rerun["input_fingerprint"] == first_run["input_fingerprint"]
    assert rerun["metrics"] == first_run["metrics"]

    # 4. A CSV for another period: review the proposed mapping, confirm, and see the
    #    normalised figures in base units.
    csv = b"label,amount\nSales,(900)\nCost of revenue,500\nNet income,20\n"
    imported = alice.call(
        "post",
        f"{E}/imports/",
        {
            **FY2024,
            "statement_type": "income_statement",
            "currency": "INR",
            "reported_scale": "crores",
            "file": SimpleUploadedFile("fy24.csv", csv, "text/csv"),
        },
        status=201,
        multipart=True,
    )
    assert [r["line_item_code"] for r in imported["line_items"]] == [
        None,  # "Sales" is no exact name: the user maps it
        "cost_of_revenue",
        "net_income",
    ]
    sales = imported["line_items"][0]
    mapped = alice.call(
        "patch",
        f"{W}/statements/{imported['id']}/line-items/{sales['id']}/",
        {"line_item_code": "revenue"},
        status=200,
    )
    assert mapped == {**sales, "line_item_code": "revenue"}  # the file's "(900)" survives review

    # 5. A negative revenue and an unbalanced balance sheet are warnings that never
    #    block validation or the analysis.
    income_2024 = alice.call("post", f"{W}/statements/{imported['id']}/validate/", status=200)
    assert [i["code"] for i in income_2024["issues"]] == ["unexpected_sign"]
    assert {f["line_item"]: f["value"] for f in income_2024["facts"]}["revenue"] == (
        "-9000000000.000000"
    )
    balance_2024 = alice.call(
        "post",
        f"{E}/statements/",
        {
            **FY2024,
            "statement_type": "balance_sheet",
            "currency": "INR",
            "reported_scale": "crores",
            "line_items": rows(total_assets="1000", total_liabilities="600", total_equity="300"),
        },
        status=201,
    )
    balance_2024 = alice.call("post", f"{W}/statements/{balance_2024['id']}/validate/", status=200)
    assert [i["code"] for i in balance_2024["issues"]] == ["balance_sheet_imbalance"]
    run_2024 = alice.call("post", f"{E}/analyses/", FY2024, status=201)
    assert {i["code"] for i in run_2024["issues"]} == {"unexpected_sign", "balance_sheet_imbalance"}

    # 9. A figure traces to its source row, its statement version and its document.
    revenue_input = next(i for i in run_2024["inputs"] if i["line_item"] == "revenue")
    sales_row = next(r for r in income_2024["line_items"] if r["label"] == "Sales")
    assert (revenue_input["row_id"], sales_row["source_reference"]) == (sales_row["id"], "line 2")
    assert (revenue_input["statement_id"], revenue_input["statement_version"]) == (
        imported["id"],
        1,
    )
    assert revenue_input["document_id"] == imported["document"]["id"]

    # 8. Correcting a figure creates version 2; the earlier analysis keeps its inputs
    #    and results.
    income_2025 = statements["income_statement"]
    restated = alice.call(
        "post",
        f"{W}/statements/{income_2025['id']}/restatements/",
        {"reason": "Audited figures", "line_items": rows(revenue="1000", net_income="120")},
        status=201,
    )
    assert (restated["version"], restated["supersedes_id"]) == (2, income_2025["id"])
    alice.call("post", f"{W}/statements/{restated['id']}/validate/", status=200)
    earlier = alice.call("get", f"{R}/{first_run['id']}/", status=200)
    assert earlier["metrics"] == first_run["metrics"]
    assert earlier["uses_superseded_statement"] is True
    corrected = alice.call("post", f"{E}/analyses/", FY2025, status=201)
    assert {m["code"]: m["value"] for m in corrected["metrics"]}["net_margin"] == "0.120000"

    # 10. Unauthenticated calls get 401 in the envelope; another workspace's data is 404.
    anonymous = Browser()
    anonymous.call("get", "/api/v1/me/", status=401)
    anonymous.call("get", f"{E}/", status=401)
    bob.call("get", f"/api/v1/workspaces/{me['personal_workspace_id']}/", status=404)
    carol.call("get", f"{E}/", status=404)
    carol.call("get", f"{R}/{first_run['id']}/", status=404)
    assert bob.call("get", f"{R}/{first_run['id']}/", status=200)["id"] == first_run["id"]
