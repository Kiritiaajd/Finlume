from typing import TYPE_CHECKING

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User

# UserAdmin is generic only in django-stubs; it is not subscriptable at runtime.
if TYPE_CHECKING:
    _UserAdminBase = UserAdmin[User]
else:
    _UserAdminBase = UserAdmin


@admin.register(User)
class FinlumeUserAdmin(_UserAdminBase):
    readonly_fields = ("public_id", "last_login", "date_joined")
