"""Assembling one analysis input from stored statements (rule A2, FOUNDATION_AUDIT FA-02)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.financial_records.models import (
    FinancialFact,
    FinancialStatement,
    ReviewStatus,
    StatementStatus,
)
from domain.calculations import run_statement_analysis
from domain.financial_statements import LineItem, PeriodType, ReportingPeriod
from domain.validation import IssueCode
from services.errors import ConflictError
from services.statement_analysis import assemble_analysis_input, build_facts

pytestmark = pytest.mark.django_db

FY2025 = ReportingPeriod(date(2025, 1, 1), date(2025, 12, 31), PeriodType.ANNUAL)
VALIDATED, DRAFT, SUPERSEDED = (
    StatementStatus.VALIDATED,
    StatementStatus.DRAFT,
    StatementStatus.SUPERSEDED,
)


@pytest.fixture
def entity(make_entity):
    return make_entity()


@pytest.fixture
def stored(make_statement, restate, make_line_item):
    """A statement with one raw row per figure, normalised and saved as confirmed facts.

    Figures are in thousands, as entered; facts hold base units.
    """

    def build(entity, statement_type, *, restating=None, **figures):
        fields = {"status": figures.pop("status", VALIDATED)}
        if "currency" in figures:
            fields["currency"] = figures.pop("currency")
        statement = (
            restate(restating, **fields)
            if restating
            else make_statement(entity=entity, statement_type=statement_type, **fields)
        )
        for code, amount in figures.items():
            make_line_item(statement, code, amount)
        FinancialFact.objects.bulk_create(
            build_facts(statement, review_status=ReviewStatus.CONFIRMED)
        )
        return statement

    return build


def test_the_three_statements_of_a_period_combine_into_one_fact_set(entity, stored):
    income = stored(entity, "income_statement", revenue="1000", net_income="100")
    balance = stored(entity, "balance_sheet", total_assets="1200", total_equity="500")
    cash = stored(entity, "cash_flow", net_cash_from_operating_activities="150")

    assembled = assemble_analysis_input(entity=entity, period=FY2025)

    assert assembled.facts.period == FY2025
    assert str(assembled.facts.currency) == "USD"
    assert dict(assembled.facts.values) == {
        LineItem.REVENUE: Decimal("1000000"),
        LineItem.NET_INCOME: Decimal("100000"),
        LineItem.TOTAL_ASSETS: Decimal("1200000"),
        LineItem.TOTAL_EQUITY: Decimal("500000"),
        LineItem.NET_CASH_FROM_OPERATING_ACTIVITIES: Decimal("150000"),
    }
    assert {s.pk for s in assembled.statements} == {income.pk, balance.pk, cash.pk}
    assert len(assembled.source_facts) == 5


def test_a_combined_input_feeds_cross_statement_ratios(entity, stored):
    stored(entity, "income_statement", revenue="1000", net_income="100")
    stored(entity, "balance_sheet", total_assets="1200", total_equity="500")

    outcome = run_statement_analysis(assemble_analysis_input(entity=entity, period=FY2025).facts)

    roe = next(m for m in outcome.metrics if m.code == "return_on_equity")
    assert roe.value == Decimal("0.200000")


def test_a_missing_statement_type_is_allowed_and_reported_by_the_engine(entity, stored):
    stored(entity, "income_statement", revenue="1000", net_income="100")

    outcome = run_statement_analysis(assemble_analysis_input(entity=entity, period=FY2025).facts)

    roe = next(m for m in outcome.metrics if m.code == "return_on_equity")
    assert roe.value is None
    assert roe.issues[0].code == IssueCode.MISSING_INPUT


def test_assembly_costs_two_queries(entity, stored, django_assert_num_queries):
    stored(entity, "income_statement", revenue="1000")
    stored(entity, "balance_sheet", total_assets="1200")

    with django_assert_num_queries(2):
        assemble_analysis_input(entity=entity, period=FY2025)


# --- Which versions and facts are used ------------------------------------------------


def test_a_draft_restatement_is_ignored_until_it_is_validated(entity, stored):
    v1 = stored(entity, "income_statement", revenue="1000")
    v2 = stored(entity, "income_statement", restating=v1, status=DRAFT, revenue="1100")

    assert assemble_analysis_input(entity=entity, period=FY2025).facts.get(
        LineItem.REVENUE
    ) == Decimal("1000000")

    # Validating the restatement: supersede version 1 first, then validate version 2.
    FinancialStatement.objects.filter(pk=v1.pk).update(status=SUPERSEDED)
    FinancialStatement.objects.filter(pk=v2.pk).update(status=VALIDATED)

    assembled = assemble_analysis_input(entity=entity, period=FY2025)
    assert assembled.facts.get(LineItem.REVENUE) == Decimal("1100000")
    assert [s.version for s in assembled.statements] == [2]


@pytest.mark.parametrize("status", [ReviewStatus.UNREVIEWED, ReviewStatus.REJECTED])
def test_only_confirmed_facts_are_used(entity, stored, status):
    statement = stored(entity, "income_statement", revenue="1000", net_income="100")
    FinancialFact.objects.filter(statement=statement, line_item="net_income").update(
        review_status=status
    )

    facts = assemble_analysis_input(entity=entity, period=FY2025).facts

    assert set(facts.values) == {LineItem.REVENUE}


@pytest.mark.parametrize(
    "elsewhere",
    ["another period", "another period type", "another entity", "another workspace"],
)
def test_statements_outside_the_entity_and_exact_period_are_not_used(
    entity, stored, make_statement, make_line_item, make_entity, elsewhere
):
    stored(entity, "income_statement", revenue="1000")
    if elsewhere == "another period":
        other = make_statement(
            entity=entity,
            statement_type="balance_sheet",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 12, 31),
        )
    elif elsewhere == "another period type":
        other = make_statement(entity=entity, statement_type="balance_sheet", period_type="other")
    elif elsewhere == "another entity":
        other = make_statement(
            entity=make_entity(workspace=entity.workspace), statement_type="balance_sheet"
        )
    else:
        other = make_statement(statement_type="balance_sheet")  # its own workspace
    make_line_item(other, "total_assets", "9")
    FinancialFact.objects.bulk_create(build_facts(other, review_status=ReviewStatus.CONFIRMED))

    assembled = assemble_analysis_input(entity=entity, period=FY2025)

    assert set(assembled.facts.values) == {LineItem.REVENUE}
    assert len(assembled.statements) == 1


# --- Refusals ---------------------------------------------------------------------------


def test_statements_in_different_currencies_are_refused(entity, stored):
    stored(entity, "income_statement", revenue="1000", currency="USD")
    stored(entity, "balance_sheet", total_assets="1200", currency="EUR")

    with pytest.raises(ConflictError, match="different currencies: EUR, USD"):
        assemble_analysis_input(entity=entity, period=FY2025)


@pytest.mark.parametrize("status", [DRAFT, SUPERSEDED])
def test_a_period_without_a_validated_statement_is_refused(entity, stored, status):
    stored(entity, "income_statement", status=status, revenue="1000")

    with pytest.raises(ConflictError, match="No validated statement"):
        assemble_analysis_input(entity=entity, period=FY2025)


def test_a_figure_stored_on_the_wrong_statement_type_is_refused(
    entity, make_statement, make_line_item, make_fact
):
    # The database does not tie a code to its statement type (DATA_MODEL §4.7).
    income = make_statement(entity=entity, statement_type="income_statement")
    make_fact(make_line_item(income, "total_assets"))

    with pytest.raises(ConflictError, match="belongs on the balance_sheet"):
        assemble_analysis_input(entity=entity, period=FY2025)
