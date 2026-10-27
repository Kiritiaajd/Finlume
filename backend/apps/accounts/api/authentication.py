"""Session authentication that answers 401 with a Session challenge (ADR-0007)."""

from __future__ import annotations

from rest_framework import authentication
from rest_framework.request import Request

SESSION_CHALLENGE = "Session"


class SessionAuthentication(authentication.SessionAuthentication):
    """DRF's session authentication, plus a ``WWW-Authenticate`` challenge.

    With a challenge, DRF answers unauthenticated requests ``401`` instead of
    ``403``. Signed-in users without permission, and CSRF failures, still get
    ``403``.
    """

    def authenticate_header(self, request: Request) -> str:
        return SESSION_CHALLENGE


def enforce_csrf(request: Request) -> None:
    """Apply Django's CSRF check to an anonymous request.

    DRF checks CSRF only for already signed-in sessions. Login and
    registration need it too, or another site could sign a victim into an
    attacker's account. Raises ``PermissionDenied`` (403).
    """
    authentication.SessionAuthentication().enforce_csrf(request)
