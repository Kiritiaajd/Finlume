"""Login throttles per client IP and per submitted email (ADR-0007)."""

from __future__ import annotations

import hashlib
from typing import Any

from rest_framework.request import Request
from rest_framework.throttling import SimpleRateThrottle

from apps.accounts.backends import normalize_email


class LoginIPThrottle(SimpleRateThrottle):
    """Limits sign-in attempts from one client IP."""

    scope = "login_ip"

    def get_cache_key(self, request: Request, view: Any) -> str:
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class LoginEmailThrottle(SimpleRateThrottle):
    """Limits sign-in attempts against one email address, from any IP.

    The address is hashed, so cache keys never hold raw emails.
    """

    scope = "login_email"

    def get_cache_key(self, request: Request, view: Any) -> str | None:
        email = request.data.get("email") if hasattr(request.data, "get") else None
        if not isinstance(email, str) or not email.strip():
            return None  # nothing to key on; the IP throttle still applies
        digest = hashlib.sha256(normalize_email(email).encode()).hexdigest()
        return self.cache_format % {"scope": self.scope, "ident": digest}
