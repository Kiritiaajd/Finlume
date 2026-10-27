from typing import TYPE_CHECKING

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.http import HttpRequest

from .models import User

# UserAdmin is generic only in django-stubs; it is not subscriptable at runtime.
if TYPE_CHECKING:
    _UserAdminBase = UserAdmin[User]
else:
    _UserAdminBase = UserAdmin


@admin.register(User)
class FinlumeUserAdmin(_UserAdminBase):
    readonly_fields = ("public_id", "last_login", "date_joined")

    def has_delete_permission(self, request: HttpRequest, obj: User | None = None) -> bool:
        # Deleting a user cascades into their workspaces and memberships, bypassing
        # the ownership rules. It waits for the account-deletion workflow (ADR-0008 §7).
        return False
