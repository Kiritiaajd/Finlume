from __future__ import annotations

import contextlib
import itertools
import os
from datetime import date
from decimal import Decimal

import pytest
from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.organizations.models import Organization, OrganizationMembership, OrganizationRole
from apps.workspaces.models import Workspace, WorkspaceMembership, WorkspaceRole
from domain.financial_statements import (
    Currency,
    FinancialFactSet,
    LineItem,
    PeriodType,
    ReportingPeriod,
)


def pytest_collection_modifyitems(config, items):
    """Skip ``@pytest.mark.postgres`` tests unless the suite runs on PostgreSQL.

    With FINLUME_REQUIRE_POSTGRES_TESTS set (as in CI), refuse to run at all on
    another database, so PostgreSQL coverage can never be lost silently.
    """
    if settings.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql":
        return
    if os.environ.get("FINLUME_REQUIRE_POSTGRES_TESTS"):
        raise pytest.UsageError(
            "FINLUME_REQUIRE_POSTGRES_TESTS is set but the tests are not using PostgreSQL. "
            "Set FINLUME_TEST_DB_ENGINE=postgresql and the POSTGRES_* variables."
        )
    skip = pytest.mark.skip(reason="requires PostgreSQL (set FINLUME_TEST_DB_ENGINE=postgresql)")
    for item in items:
        if "postgres" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture(autouse=True)
def _isolated_cache():
    """Throttle counters live in the cache; start every test from zero."""
    cache.clear()


# Per-request plumbing every authenticated call pays, whatever the endpoint:
# transaction savepoints (ATOMIC_REQUESTS), the session read and its sliding-
# expiry write, and loading the signed-in user.
_PLUMBING_SQL = (
    "SAVEPOINT",
    "RELEASE SAVEPOINT",
    'SELECT "django_session"',
    'UPDATE "django_session"',
    'SELECT "accounts_user"',
)


@pytest.fixture
def assert_app_queries():
    """Assert how many queries an endpoint's own code runs, ignoring _PLUMBING_SQL."""

    @contextlib.contextmanager
    def check(expected: int):
        with CaptureQueriesContext(connection) as context:
            yield
        app_sql = [
            q["sql"] for q in context.captured_queries if not q["sql"].startswith(_PLUMBING_SQL)
        ]
        assert len(app_sql) == expected, "\n\n".join(app_sql)

    return check


# --- Tenancy builders (fictional data only) ----------------------------------
# Plain ORM writes, until the services that own these writes exist.


@pytest.fixture
def make_user(db):
    numbers = itertools.count(1)

    def build(**fields) -> User:
        n = next(numbers)
        return User.objects.create_user(f"user{n}", email=f"user{n}@example.com", **fields)

    return build


@pytest.fixture
def make_organization(make_user):
    """An organization whose given (or new) user is its admin."""

    def build(admin: User | None = None, name: str = "Example Org") -> Organization:
        admin = admin or make_user()
        organization = Organization.objects.create(name=name, created_by=admin)
        OrganizationMembership.objects.create(
            organization=organization, user=admin, role=OrganizationRole.ADMIN
        )
        return organization

    return build


@pytest.fixture
def make_workspace(make_user, make_organization):
    """An organization workspace with ``owner`` (or a new user) as its owner."""

    def build(organization: Organization | None = None, owner: User | None = None) -> Workspace:
        owner = owner or make_user()
        organization = organization or make_organization(admin=owner)
        workspace = Workspace.objects.create(
            name="Example Workspace", organization=organization, created_by=owner
        )
        WorkspaceMembership.objects.create(
            workspace=workspace, user=owner, role=WorkspaceRole.OWNER
        )
        return workspace

    return build


@pytest.fixture
def add_to_workspace(make_user):
    """Make ``user`` (or a new user) a member of the workspace's organization and the workspace."""

    def build(workspace: Workspace, role: WorkspaceRole, user: User | None = None) -> User:
        user = user or make_user()
        OrganizationMembership.objects.get_or_create(
            organization_id=workspace.organization_id,
            user=user,
            defaults={"role": OrganizationRole.MEMBER},
        )
        WorkspaceMembership.objects.create(workspace=workspace, user=user, role=role)
        return user

    return build


@pytest.fixture
def fy2025() -> ReportingPeriod:
    return ReportingPeriod(date(2025, 1, 1), date(2025, 12, 31), PeriodType.ANNUAL)


@pytest.fixture
def make_facts(fy2025):
    """Build a FinancialFactSet in USD for FY2025 from ``line_item=value`` pairs."""

    def build(**values: str) -> FinancialFactSet:
        return FinancialFactSet(
            currency=Currency("USD"),
            period=fy2025,
            values={LineItem(code): Decimal(amount) for code, amount in values.items()},
        )

    return build


@pytest.fixture
def complete_facts(make_facts) -> FinancialFactSet:
    """A small, internally consistent fictional company (no real data)."""
    return make_facts(
        revenue="1000000",
        cost_of_revenue="600000",
        gross_profit="400000",
        operating_income="150000",
        net_income="100000",
        total_current_assets="500000",
        total_current_liabilities="250000",
        total_assets="1200000",
        total_liabilities="700000",
        total_debt="300000",
        total_equity="500000",
    )
