"""Every registered endpoint is authenticated and tenant-isolated (MVP step 6).

The endpoints come from Django's URL resolver, the authoritative registry, not
from a hand-kept list: a new endpoint is covered the moment it is routed. A
route parameter without a recipe below fails the test, so it can never be
silently skipped.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pytest
from django.urls import URLPattern, URLResolver, get_resolver
from django.views import View

from apps.organizations.models import OrganizationMembership, OrganizationRole
from apps.workspaces.models import WorkspaceRole
from domain.financial_statements import PeriodType, ReportingPeriod
from services.statement_analysis import (
    create_entity,
    create_report,
    create_statement,
    run_analysis,
    validate_statement,
)

from .contract import contract

pytestmark = pytest.mark.django_db

#: Endpoints anyone may call. Adding one here is a deliberate, reviewed decision.
PUBLIC = {
    ("get", "/api/v1/health/"),
    ("get", "/api/v1/auth/csrf/"),
    ("post", "/api/v1/auth/register/"),
    ("post", "/api/v1/auth/login/"),
}

FY = ReportingPeriod(date(2025, 1, 1), date(2025, 12, 31), PeriodType.ANNUAL)


@dataclass(frozen=True)
class Endpoint:
    template: str  # e.g. /api/v1/workspaces/{workspace_id}/reports/{report_id}/
    method: str

    @property
    def params(self) -> list[str]:
        return re.findall(r"{(\w+)}", self.template)

    def url(self, values: dict[str, object]) -> str:
        return self.template.format(**{name: values[name] for name in self.params})


def _routes(patterns: list, prefix: str = "") -> list[tuple[str, type[View]]]:
    found: list[tuple[str, type[View]]] = []
    for pattern in patterns:
        route = prefix + str(pattern.pattern)
        if isinstance(pattern, URLResolver):
            found += _routes(pattern.url_patterns, route)
        elif isinstance(pattern, URLPattern) and hasattr(pattern.callback, "view_class"):
            found.append((route, pattern.callback.view_class))
    return found


def api_endpoints() -> list[Endpoint]:
    """Every method of every routed API view, from the URL resolver."""
    endpoints = []
    for route, view in _routes(get_resolver().url_patterns):
        if not route.startswith("^api/"):
            continue  # the Django admin has its own protection
        template = "/" + re.sub(
            r"<(?:\w+:)?(\w+)>", r"{\1}", route.replace("^", "").replace("(?P<version>v1)", "v1")
        )
        for method in view.http_method_names:
            if method not in ("options", "head") and hasattr(view, method):
                endpoints.append(Endpoint(template, method))
    return endpoints


ENDPOINTS = api_endpoints()
WITH_IDS = [e for e in ENDPOINTS if e.params]


def test_the_registry_finds_every_documented_operation_and_nothing_undocumented():
    routed = {(e.method, e.template) for e in ENDPOINTS} - {("get", "/api/v1/schema/")}
    documented = {
        (method, path) for path, operations in contract()["paths"].items() for method in operations
    }

    assert routed == documented
    assert len(routed) >= 40


# --- Fixtures: two workspaces with one of everything ----------------------------------------


def _world(make_workspace, make_user):
    """A workspace with an entity, a validated statement, a run, a report and a second member."""
    workspace = make_workspace()
    owner = workspace.memberships.get().user
    entity = create_entity(
        actor=owner, workspace=workspace, name="Example Co", entity_type="business"
    )
    statement = create_statement(
        actor=owner,
        workspace=workspace,
        entity=entity,
        statement_type="income_statement",
        period_start=FY.start,
        period_end=FY.end,
        period_type="annual",
        currency="USD",
        reported_scale="units",
        rows=[
            {
                "label": "Revenue",
                "line_item_code": "revenue",
                "amount": Decimal("100"),
                "raw_value": "100",
                "source_reference": "",
            }
        ],
    )
    validate_statement(actor=owner, workspace=workspace, statement=statement)
    run = run_analysis(actor=owner, workspace=workspace, entity=entity, period=FY)
    report = create_report(
        actor=owner, workspace=workspace, title="Review", notes="", run_ids=[run.public_id]
    )
    member = make_user()
    OrganizationMembership.objects.create(
        organization=workspace.organization, user=member, role=OrganizationRole.MEMBER
    )
    workspace.memberships.create(user=member, role=WorkspaceRole.VIEWER)
    return {
        "owner": owner,
        "workspace_id": workspace.public_id,
        "organization_id": workspace.organization.public_id,
        "entity_id": entity.public_id,
        "statement_id": statement.public_id,
        "row_id": statement.line_items.get().public_id,
        "run_id": run.public_id,
        "report_id": report.public_id,
        "user_id": member.public_id,
    }


@pytest.fixture
def mine(make_workspace, make_user):
    return _world(make_workspace, make_user)


@pytest.fixture
def theirs(make_workspace, make_user):
    return _world(make_workspace, make_user)


def _require_recipes(endpoint: Endpoint, values: dict[str, object]) -> None:
    missing = [name for name in endpoint.params if name not in values]
    if missing:
        pytest.fail(
            f"{endpoint.method.upper()} {endpoint.template}: no recipe for {missing}. "
            "Add one to _world so the new endpoint's isolation is tested."
        )


#: Valid bodies for endpoints that validate them before looking anything up, so
#: the lookup, not the validation, decides. A missing entry fails with 400, never
#: passes silently.
BODIES = {
    ("patch", "/api/v1/organizations/{organization_id}/members/{user_id}/"): {"role": "member"},
    ("patch", "/api/v1/workspaces/{workspace_id}/members/{user_id}/"): {"role": "viewer"},
}


def _call(client, endpoint: Endpoint, values: dict[str, object]):
    body = BODIES.get((endpoint.method, endpoint.template), {})
    return getattr(client, endpoint.method)(endpoint.url(values), body, format="json")


# --- Authentication -------------------------------------------------------------------------


@pytest.mark.parametrize("endpoint", ENDPOINTS, ids=lambda e: f"{e.method} {e.template}")
def test_every_endpoint_but_the_public_ones_requires_sign_in(api_client, endpoint):
    if (endpoint.method, endpoint.template) in PUBLIC:
        pytest.skip("public by design")

    response = _call(api_client, endpoint, {name: uuid.uuid4() for name in endpoint.params})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


# --- Isolation --------------------------------------------------------------------------------


@pytest.mark.parametrize("endpoint", WITH_IDS, ids=lambda e: f"{e.method} {e.template}")
def test_an_outsider_cannot_reach_anything_of_another_tenant(
    api_client, make_user, theirs, endpoint
):
    _require_recipes(endpoint, theirs)
    api_client.force_login(make_user())  # signed in, but a member of nothing here

    response = _call(api_client, endpoint, theirs)

    assert response.status_code == 404


@pytest.mark.parametrize(
    "endpoint",
    [e for e in WITH_IDS if len(e.params) > 1],
    ids=lambda e: f"{e.method} {e.template}",
)
def test_ids_from_another_tenant_are_not_found_inside_my_own(api_client, mine, theirs, endpoint):
    """My workspace or organization in the URL, someone else's object after it."""
    _require_recipes(endpoint, theirs)
    api_client.force_login(mine["owner"])  # owner of my workspace, admin of my organization
    values = {
        **theirs,
        "workspace_id": mine["workspace_id"],
        "organization_id": mine["organization_id"],
    }

    response = _call(api_client, endpoint, values)

    assert response.status_code == 404
