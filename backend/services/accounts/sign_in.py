"""What happens around a sign-in attempt: provisioning and the audit trail.

Verifying credentials and starting the session are HTTP concerns handled by
the API view (Django's ``authenticate`` and ``login``); these workflows run
after them.
"""

from __future__ import annotations

from apps.accounts.backends import normalize_email
from apps.accounts.models import User
from apps.audit.models import AuditEvent

from .registration import ensure_personal_workspace


def complete_sign_in(user: User) -> None:
    ensure_personal_workspace(user)
    AuditEvent.record("auth.login", actor=user)


def record_failed_sign_in(email: str) -> None:
    """Audit a failed attempt. Only the normalised email is kept, never the password."""
    AuditEvent.record("auth.login_failed", email=normalize_email(email))
