"""The single JSON error envelope used by every API response.

    {"error": {"code": "...", "message": "...", "details": ..., "request_id": "..."}}

``code`` is a stable machine-readable string; ``message`` is safe to show to
users; ``details`` carries field-level validation errors when present.
Internal exception text, stack traces and SQL never reach the client.
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions
from rest_framework.response import Response
from rest_framework.views import exception_handler

from .request_context import get_request_id


def error_body(code: str, message: str, details: Any = None) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "request_id": get_request_id(),
        }
    }


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """Wrap DRF's handler so known API errors use the Finlume envelope.

    Unexpected exceptions return ``None`` and propagate to Django, which logs
    them, rolls back the request transaction and answers through
    ``apps.core.views.server_error``.
    """
    response = exception_handler(exc, context)
    if response is None:
        return None

    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = exceptions.PermissionDenied()

    if isinstance(exc, exceptions.ValidationError):
        response.data = error_body("validation_error", "The request is invalid.", response.data)
        return response

    if isinstance(exc, exceptions.ParseError):
        # DRF's parse errors embed parser internals (e.g. JSON decoder text).
        response.data = error_body("parse_error", "The request body could not be parsed.")
        return response

    if isinstance(exc, exceptions.APIException):
        detail = exc.detail
        code = getattr(detail, "code", None) or exc.default_code
        message = str(detail) if isinstance(detail, str) else str(exc.default_detail)
        response.data = error_body(str(code), message)
    return response
