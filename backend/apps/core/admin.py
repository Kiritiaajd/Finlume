"""Shared admin base classes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.contrib import admin
from django.http import HttpRequest

# ModelAdmin is generic only in django-stubs; it is not subscriptable at runtime.
if TYPE_CHECKING:
    _ModelAdminBase = admin.ModelAdmin[Any]
else:
    _ModelAdminBase = admin.ModelAdmin


class ReadOnlyModelAdmin(_ModelAdminBase):
    """Lets staff inspect rows but never add, change or delete them.

    Used where writes must go through use cases that enforce cross-table
    invariants, such as tenancy (ADR-0008 §7).
    """

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False
