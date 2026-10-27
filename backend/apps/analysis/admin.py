"""Read-only admin for analysis runs. Runs are immutable (DATA_MODEL §4.9)."""

from __future__ import annotations

from django.contrib import admin

from apps.core.admin import ReadOnlyModelAdmin

from .models import AnalysisRun


@admin.register(AnalysisRun)
class AnalysisRunAdmin(ReadOnlyModelAdmin):
    list_display = (
        "public_id",
        "entity",
        "period_start",
        "period_end",
        "currency",
        "engine_version",
        "created_at",
    )
    list_filter = ("engine_version",)
    list_select_related = ("entity",)
    search_fields = ("input_fingerprint",)
