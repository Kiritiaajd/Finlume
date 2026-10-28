"""The ``Idempotency-Key`` request header (API conventions, Idempotency)."""

from __future__ import annotations

from uuid import UUID

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request

#: The header as documented in the OpenAPI schema.
IDEMPOTENCY_KEY = OpenApiParameter(
    "Idempotency-Key",
    OpenApiTypes.UUID,
    OpenApiParameter.HEADER,
    required=False,
    description=(
        "A client-generated UUID. Repeating it with the same request returns the "
        "original result; with a different request, 409."
    ),
)


def idempotency_key(request: Request) -> UUID | None:
    """The request's key, or ``None``. A key that is not a UUID is a ``400``."""
    value = request.headers.get("Idempotency-Key")
    if value is None:
        return None
    try:
        return UUID(value)
    except ValueError:
        raise ValidationError({"Idempotency-Key": ["Use a UUID."]}) from None
