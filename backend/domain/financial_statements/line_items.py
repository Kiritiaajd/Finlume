"""Finlume's canonical line-item taxonomy for the MVP.

Codes are stable identifiers: they are persisted and appear in the API, so a
code is never renamed or reused; retire it and add a new one instead.

Sign convention (normalised data): revenues, expenses, assets, liabilities
and debt are positive magnitudes. Profit lines, equity and cash-flow lines
are signed: losses, negative equity and cash outflows are negative.
"""

from __future__ import annotations

from enum import Enum, StrEnum


class StatementType(Enum):
    INCOME_STATEMENT = "income_statement"
    BALANCE_SHEET = "balance_sheet"
    CASH_FLOW = "cash_flow"


class LineItem(StrEnum):
    # Income statement (flows over the period)
    REVENUE = "revenue"
    COST_OF_REVENUE = "cost_of_revenue"
    GROSS_PROFIT = "gross_profit"
    OPERATING_EXPENSES = "operating_expenses"
    OPERATING_INCOME = "operating_income"
    INTEREST_EXPENSE = "interest_expense"
    INCOME_BEFORE_TAX = "income_before_tax"
    INCOME_TAX_EXPENSE = "income_tax_expense"
    NET_INCOME = "net_income"

    # Balance sheet (position at period end)
    CASH_AND_CASH_EQUIVALENTS = "cash_and_cash_equivalents"
    INVENTORIES = "inventories"
    TOTAL_CURRENT_ASSETS = "total_current_assets"
    TOTAL_ASSETS = "total_assets"
    TOTAL_CURRENT_LIABILITIES = "total_current_liabilities"
    TOTAL_LIABILITIES = "total_liabilities"
    TOTAL_DEBT = "total_debt"
    TOTAL_EQUITY = "total_equity"

    # Cash flow statement (flows over the period)
    NET_CASH_FROM_OPERATING_ACTIVITIES = "net_cash_from_operating_activities"
    CAPITAL_EXPENDITURE = "capital_expenditure"
    NET_CASH_FROM_INVESTING_ACTIVITIES = "net_cash_from_investing_activities"
    NET_CASH_FROM_FINANCING_ACTIVITIES = "net_cash_from_financing_activities"

    @property
    def statement_type(self) -> StatementType:
        return _STATEMENT_OF[self]


_INCOME = StatementType.INCOME_STATEMENT
_BALANCE = StatementType.BALANCE_SHEET
_CASH = StatementType.CASH_FLOW

_STATEMENT_OF: dict[LineItem, StatementType] = {
    LineItem.REVENUE: _INCOME,
    LineItem.COST_OF_REVENUE: _INCOME,
    LineItem.GROSS_PROFIT: _INCOME,
    LineItem.OPERATING_EXPENSES: _INCOME,
    LineItem.OPERATING_INCOME: _INCOME,
    LineItem.INTEREST_EXPENSE: _INCOME,
    LineItem.INCOME_BEFORE_TAX: _INCOME,
    LineItem.INCOME_TAX_EXPENSE: _INCOME,
    LineItem.NET_INCOME: _INCOME,
    LineItem.CASH_AND_CASH_EQUIVALENTS: _BALANCE,
    LineItem.INVENTORIES: _BALANCE,
    LineItem.TOTAL_CURRENT_ASSETS: _BALANCE,
    LineItem.TOTAL_ASSETS: _BALANCE,
    LineItem.TOTAL_CURRENT_LIABILITIES: _BALANCE,
    LineItem.TOTAL_LIABILITIES: _BALANCE,
    LineItem.TOTAL_DEBT: _BALANCE,
    LineItem.TOTAL_EQUITY: _BALANCE,
    LineItem.NET_CASH_FROM_OPERATING_ACTIVITIES: _CASH,
    LineItem.CAPITAL_EXPENDITURE: _CASH,
    LineItem.NET_CASH_FROM_INVESTING_ACTIVITIES: _CASH,
    LineItem.NET_CASH_FROM_FINANCING_ACTIVITIES: _CASH,
}

#: Items that are positive magnitudes under the sign convention above.
NON_NEGATIVE_ITEMS: frozenset[LineItem] = frozenset(
    {
        LineItem.REVENUE,
        LineItem.COST_OF_REVENUE,
        LineItem.OPERATING_EXPENSES,
        LineItem.INTEREST_EXPENSE,
        LineItem.CASH_AND_CASH_EQUIVALENTS,
        LineItem.INVENTORIES,
        LineItem.TOTAL_CURRENT_ASSETS,
        LineItem.TOTAL_ASSETS,
        LineItem.TOTAL_CURRENT_LIABILITIES,
        LineItem.TOTAL_LIABILITIES,
        LineItem.TOTAL_DEBT,
    }
)

#: Items that are cash outflows and therefore zero or negative.
NON_POSITIVE_ITEMS: frozenset[LineItem] = frozenset({LineItem.CAPITAL_EXPENDITURE})
