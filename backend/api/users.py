"""The signed-in user of a request, typed."""

from __future__ import annotations

from rest_framework.exceptions import NotAuthenticated
from rest_framework.request import Request

from apps.accounts.models import User


def request_user(request: Request) -> User:
    """``request.user`` as a ``User``. Raises ``NotAuthenticated`` (401) for anonymous requests.

    Views behind ``IsAuthenticated`` never hit the raise; it narrows the type
    and guards views that forget their permission class.
    """
    user = request.user
    if not isinstance(user, User):
        raise NotAuthenticated
    return user
