"""Builders for report tests: runs of one fictional company, reusing the analysis builders."""

from __future__ import annotations

import pytest

from services.statement_analysis import run_analysis
from tests.analysis import conftest as analysis

# Binding them here registers them as fixtures for this package.
make_entity = analysis.make_entity
make_fact = analysis.make_fact
make_line_item = analysis.make_line_item
make_source = analysis.make_source
make_statement = analysis.make_statement
restate = analysis.restate
workspace = analysis.workspace
owner = analysis.owner
entity = analysis.entity
validated = analysis.validated


@pytest.fixture
def make_run(validated, owner, workspace, entity):
    """A new run of FY2025; the first call validates the company's statements."""
    state = {"ready": False}

    def build():
        if not state["ready"]:
            validated("income_statement", analysis.INCOME)
            validated("balance_sheet", analysis.BALANCE)
            state["ready"] = True
        return run_analysis(actor=owner, workspace=workspace, entity=entity, period=analysis.FY2025)

    return build
