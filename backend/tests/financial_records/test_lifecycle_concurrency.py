"""Validating and restating one statement concurrently keeps the chain consistent.

PostgreSQL only: SQLite has no row locks (``SELECT ... FOR UPDATE``).
"""

from __future__ import annotations

import threading

import pytest
from django.db import connection

from apps.financial_records.models import FinancialFact, FinancialStatement, StatementStatus
from services.errors import ConflictError
from services.statement_analysis import restate_statement, validate_statement

pytestmark = [pytest.mark.postgres, pytest.mark.django_db(transaction=True)]


def run_together(*calls):
    """Start every call at the same moment, each on its own connection; return outcomes."""
    start = threading.Barrier(len(calls))
    outcomes: list[str] = []

    def run(call):
        try:
            start.wait()
            call()
            outcomes.append("done")
        except ConflictError:
            outcomes.append("conflict")
        finally:
            connection.close()

    threads = [threading.Thread(target=run, args=(call,)) for call in calls]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    return sorted(outcomes)


@pytest.fixture
def setup(make_workspace, make_entity):
    workspace = make_workspace()
    return workspace.memberships.get().user, workspace, make_entity(workspace=workspace)


def test_validating_one_draft_twice_at_once_validates_it_once(
    setup, make_statement, make_line_item
):
    actor, workspace, entity = setup
    draft = make_statement(entity=entity, status=StatementStatus.DRAFT)
    make_line_item(draft, "revenue", "10")

    def validate():
        validate_statement(actor=actor, workspace=workspace, statement=draft)

    assert run_together(validate, validate) == ["conflict", "done"]
    assert FinancialStatement.objects.get(pk=draft.pk).status == StatementStatus.VALIDATED
    assert FinancialFact.objects.count() == 1


def test_restating_one_statement_twice_at_once_starts_one_restatement(
    setup, make_statement, make_line_item
):
    actor, workspace, entity = setup
    current = make_statement(entity=entity, status=StatementStatus.VALIDATED)
    make_line_item(current, "revenue", "10")

    def restate():
        restate_statement(actor=actor, workspace=workspace, statement=current, reason="Fix")

    assert run_together(restate, restate) == ["conflict", "done"]
    assert FinancialStatement.objects.filter(supersedes=current).count() == 1


def test_validating_version_2_while_restating_version_1_never_forks_the_chain(
    setup, make_statement, make_line_item, restate
):
    actor, workspace, entity = setup
    v1 = make_statement(entity=entity, status=StatementStatus.VALIDATED)
    v2 = restate(v1)
    make_line_item(v2, "revenue", "10")

    outcomes = run_together(
        lambda: validate_statement(actor=actor, workspace=workspace, statement=v2),
        lambda: restate_statement(actor=actor, workspace=workspace, statement=v1, reason="Fork"),
    )

    # Whichever runs first, the restatement of version 1 is refused.
    assert outcomes == ["conflict", "done"]
    statuses = dict(FinancialStatement.objects.values_list("version", "status"))
    assert statuses == {1: StatementStatus.SUPERSEDED, 2: StatementStatus.VALIDATED}
