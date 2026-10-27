"""Read-only admin for organizations (ADR-0008 §7)."""

from __future__ import annotations

from django.contrib import admin

from apps.core.admin import ReadOnlyModelAdmin

from .models import Organization, OrganizationMembership


@admin.register(Organization)
class OrganizationAdmin(ReadOnlyModelAdmin):
    list_display = ("name", "public_id", "created_at")
    search_fields = ("name",)


@admin.register(OrganizationMembership)
class OrganizationMembershipAdmin(ReadOnlyModelAdmin):
    list_display = ("organization", "user", "role", "created_at")
    list_filter = ("role",)
    list_select_related = ("organization", "user")
