"""Builders for analysis tests: validated statements of one fictional company."""

from __future__ import annotations

from datetime import date

import pytest

from apps.financial_records.models import StatementStatus
from domain.financial_statements import PeriodType, ReportingPeriod
from services.statement_analysis import validate_statement
from tests.financial_records import conftest as records

# Reuse the statement builders (fictional data only); binding them here
# registers them as fixtures for this package.
make_entity = records.make_entity
make_fact = records.make_fact
make_line_item = records.make_line_item
make_source = records.make_source
make_statement = records.make_statement
restate = records.restate

FY2025 = ReportingPeriod(date(2025, 1, 1), date(2025, 12, 31), PeriodType.ANNUAL)

#: In thousands (the builder's default scale). Internally consistent: no warnings.
INCOME = {
    "revenue": "1000",
    "cost_of_revenue": "600",
    "gross_profit": "400",
    "operating_income": "150",
    "net_income": "100",
}
BALANCE = {
    "total_current_assets": "500",
    "total_current_liabilities": "250",
    "total_assets": "1200",
    "total_liabilities": "700",
    "total_debt": "300",
    "total_equity": "500",
}


@pytest.fixture
def workspace(make_workspace):
    return make_workspace()


@pytest.fixture
def owner(workspace):
    return workspace.memberships.get().user


@pytest.fixture
def entity(workspace, make_entity):
    return make_entity(workspace=workspace, name="Example Lending Co")


@pytest.fixture
def validated(entity, owner, make_statement, make_line_item):
    """A validated statement of ``entity`` for FY2025 with the given figures."""

    def build(statement_type, figures, **fields):
        draft = make_statement(
            entity=entity, statement_type=statement_type, status=StatementStatus.DRAFT, **fields
        )
        for row, (code, amount) in enumerate(figures.items(), start=1):
            make_line_item(draft, code, amount, row_number=row)
        return validate_statement(
            actor=owner, workspace=entity.workspace, statement=draft
        ).statement

    return build
