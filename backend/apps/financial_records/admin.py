"""Read-only admin for financial records.

Writes go through use cases (MVP step 3), which keep versions, facts and
provenance consistent; the admin only inspects.
"""

from __future__ import annotations

from django.contrib import admin

from apps.core.admin import ReadOnlyModelAdmin

from .models import FinancialFact, FinancialStatement, ReportingEntity, StatementLineItem


@admin.register(ReportingEntity)
class ReportingEntityAdmin(ReadOnlyModelAdmin):
    list_display = ("name", "entity_type", "workspace", "created_at")
    list_filter = ("entity_type",)
    list_select_related = ("workspace",)
    search_fields = ("name",)


@admin.register(FinancialStatement)
class FinancialStatementAdmin(ReadOnlyModelAdmin):
    list_display = (
        "entity",
        "statement_type",
        "period_start",
        "period_end",
        "version",
        "status",
        "currency",
    )
    list_filter = ("statement_type", "status", "period_type")
    list_select_related = ("entity",)


@admin.register(StatementLineItem)
class StatementLineItemAdmin(ReadOnlyModelAdmin):
    list_display = ("statement", "row_number", "label", "line_item_code", "reported_amount")
    list_select_related = ("statement",)


@admin.register(FinancialFact)
class FinancialFactAdmin(ReadOnlyModelAdmin):
    list_display = ("entity", "line_item", "period_end", "value", "currency", "review_status")
    list_filter = ("review_status",)
    list_select_related = ("entity",)
