"""The ``Idempotency-Key`` request header (API conventions, Idempotency)."""

from __future__ import annotations

from uuid import UUID

from rest_framework.exceptions import ValidationError
from rest_framework.request import Request


def idempotency_key(request: Request) -> UUID | None:
    """The request's key, or ``None``. A key that is not a UUID is a ``400``."""
    value = request.headers.get("Idempotency-Key")
    if value is None:
        return None
    try:
        return UUID(value)
    except ValueError:
        raise ValidationError({"Idempotency-Key": ["Use a UUID."]}) from None
