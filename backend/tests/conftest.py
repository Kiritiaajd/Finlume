from __future__ import annotations

import os
from datetime import date
from decimal import Decimal

import pytest
from django.conf import settings
from rest_framework.test import APIClient

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
