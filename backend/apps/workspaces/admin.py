"""Read-only admin for workspaces (ADR-0008 §7)."""

from __future__ import annotations

from django.contrib import admin

from apps.core.admin import ReadOnlyModelAdmin

from .models import Workspace, WorkspaceMembership


@admin.register(Workspace)
class WorkspaceAdmin(ReadOnlyModelAdmin):
    list_display = ("name", "organization", "personal_owner", "created_at")
    list_select_related = ("organization", "personal_owner")
    search_fields = ("name",)


@admin.register(WorkspaceMembership)
class WorkspaceMembershipAdmin(ReadOnlyModelAdmin):
    list_display = ("workspace", "user", "role", "created_at")
    list_filter = ("role",)
    list_select_related = ("workspace", "user")
