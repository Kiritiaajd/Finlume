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

    @property
    def definition(self) -> str:
        """What a figure must include, shown as help text where figures are entered."""
        return DEFINITIONS[self]


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

#: The meaning of each code. ``operating_income``, ``net_income``, ``total_debt``
#: and ``total_equity`` follow decision A4 (FOUNDATION_AUDIT FA-10): equity and
#: profit both include non-controlling interests, so ROE pairs like with like
#: and the balance sheet identity holds. Changing a definition changes what a
#: ratio measures, so it needs the same review as a formula.
DEFINITIONS: dict[LineItem, str] = {
    LineItem.REVENUE: (
        "Income from ordinary activities for the period, such as sales and fees, "
        "net of returns, discounts and taxes collected for others."
    ),
    LineItem.COST_OF_REVENUE: (
        "Direct cost of the goods sold or services delivered in the period, as a positive amount."
    ),
    LineItem.GROSS_PROFIT: "Revenue minus cost of revenue, as reported.",
    LineItem.OPERATING_EXPENSES: (
        "Operating costs other than cost of revenue, such as selling, general, administrative "
        "and research costs, as a positive amount."
    ),
    LineItem.OPERATING_INCOME: (
        "Operating profit as reported: profit from operations before finance costs and tax. "
        "Not recomputed as EBIT."
    ),
    LineItem.INTEREST_EXPENSE: (
        "Interest and other finance costs on borrowings for the period, as a positive amount."
    ),
    LineItem.INCOME_BEFORE_TAX: "Profit before income tax, as reported.",
    LineItem.INCOME_TAX_EXPENSE: (
        "Current and deferred income tax for the period; negative for a tax benefit."
    ),
    LineItem.NET_INCOME: (
        "Profit for the period after tax, including the share attributable to "
        "non-controlling interests; negative for a loss."
    ),
    LineItem.CASH_AND_CASH_EQUIVALENTS: (
        "Cash on hand, bank balances and short-term deposits readily convertible to cash, "
        "at period end."
    ),
    LineItem.INVENTORIES: "Goods and materials held for sale or production, at period end.",
    LineItem.TOTAL_CURRENT_ASSETS: (
        "Assets expected to be realised within twelve months, at period end."
    ),
    LineItem.TOTAL_ASSETS: "All assets, current and non-current, at period end.",
    LineItem.TOTAL_CURRENT_LIABILITIES: "Obligations due within twelve months, at period end.",
    LineItem.TOTAL_LIABILITIES: "All liabilities, current and non-current, at period end.",
    LineItem.TOTAL_DEBT: (
        "Interest-bearing borrowings at period end, current and non-current, including bank "
        "overdrafts and the current portion of long-term borrowings. Excludes lease liabilities."
    ),
    LineItem.TOTAL_EQUITY: (
        "Total equity at period end, including non-controlling interests, so that total assets "
        "equal total liabilities plus total equity; negative when liabilities exceed assets."
    ),
    LineItem.NET_CASH_FROM_OPERATING_ACTIVITIES: (
        "Net cash from operating activities for the period; negative for a net outflow."
    ),
    LineItem.CAPITAL_EXPENDITURE: (
        "Cash paid for property, plant, equipment and intangible assets in the period, "
        "as a negative amount."
    ),
    LineItem.NET_CASH_FROM_INVESTING_ACTIVITIES: (
        "Net cash from investing activities for the period, including capital expenditure; "
        "negative for a net outflow."
    ),
    LineItem.NET_CASH_FROM_FINANCING_ACTIVITIES: (
        "Net cash from financing activities for the period, such as borrowing, repayments, "
        "shares issued and dividends paid; negative for a net outflow."
    ),
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
