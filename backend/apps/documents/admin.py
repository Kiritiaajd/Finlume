"""Read-only admin for source documents."""

from __future__ import annotations

from django.contrib import admin

from apps.core.admin import ReadOnlyModelAdmin

from .models import SourceDocument


@admin.register(SourceDocument)
class SourceDocumentAdmin(ReadOnlyModelAdmin):
    list_display = ("public_id", "workspace", "kind", "created_at")
    list_filter = ("kind",)
    list_select_related = ("workspace",)
