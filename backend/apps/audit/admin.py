"""Read-only admin for audit events."""

from __future__ import annotations

from django.contrib import admin

from apps.core.admin import ReadOnlyModelAdmin

from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(ReadOnlyModelAdmin):
    list_display = ("occurred_at", "action", "actor_label", "target_type", "request_id")
    list_filter = ("action",)
    search_fields = ("actor_label", "request_id")
