"""Read-only admin for reports; they are edited through the API."""

from __future__ import annotations

from django.contrib import admin

from apps.core.admin import ReadOnlyModelAdmin

from .models import Report


@admin.register(Report)
class ReportAdmin(ReadOnlyModelAdmin):
    list_display = ("title", "workspace", "created_at", "updated_at")
    list_select_related = ("workspace",)
    search_fields = ("title",)
