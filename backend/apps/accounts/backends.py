"""Email-based authentication backend (ADR-0007)."""

from __future__ import annotations

from typing import Any

from django.contrib.auth.backends import ModelBackend
from django.db.models.functions import Lower
from django.http import HttpRequest

from .models import User


def normalize_email(email: str) -> str:
    """The form used for matching: trimmed and lower-cased."""
    return email.strip().lower()


class EmailBackend(ModelBackend):
    """Signs users in by email, regardless of case.

    The lookup filters on ``Lower("email")`` so it uses the
    ``accounts_user_email_ci_unique`` expression index. Only ``email`` is
    accepted; a ``username`` argument (as the Django admin sends) is left to
    ``ModelBackend``, which follows this backend in AUTHENTICATION_BACKENDS.
    """

    def authenticate(
        self,
        request: HttpRequest | None,
        username: str | None = None,
        password: str | None = None,
        *,
        email: str | None = None,
        **kwargs: Any,
    ) -> User | None:
        if email is None or password is None:
            return None
        try:
            user = User.objects.alias(email_lower=Lower("email")).get(
                email_lower=normalize_email(email)
            )
        except User.DoesNotExist:
            # Hash anyway, so response time does not reveal whether the email exists.
            User().set_password(password)
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
