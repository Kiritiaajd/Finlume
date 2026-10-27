"""Read-only admin for source documents.

There is deliberately no ``FileField``: a stored file is only a random
``storage_key``, so no admin widget ever asks private storage for a URL
(FOUNDATION_AUDIT FA-21).
"""

from __future__ import annotations

from django.contrib import admin

from apps.core.admin import ReadOnlyModelAdmin

from .models import SourceDocument


@admin.register(SourceDocument)
class SourceDocumentAdmin(ReadOnlyModelAdmin):
    list_display = (
        "public_id",
        "workspace",
        "kind",
        "original_filename",
        "size_bytes",
        "created_at",
    )
    list_filter = ("kind",)
    list_select_related = ("workspace",)
    search_fields = ("sha256",)
