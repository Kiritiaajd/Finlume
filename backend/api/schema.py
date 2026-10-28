"""The OpenAPI schema of the v1 API (MVP step 6).

The committed contract is ``docs/api/openapi-v1.yaml``; a test regenerates the
schema and fails when it differs. The web client's TypeScript types are
generated from that file.
"""

from __future__ import annotations

from typing import Any

from drf_spectacular.authentication import SessionScheme
from drf_spectacular.utils import inline_serializer
from drf_spectacular.views import SpectacularAPIView
from rest_framework import serializers
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.settings import api_settings


class FinlumeSessionScheme(SessionScheme):  # type: ignore[no-untyped-call]  # untyped registry
    """Documents the session cookie of ``apps.accounts.api.authentication`` (ADR-0007).

    Registered when this module is imported, which loading the URL
    configuration does before any schema is generated.
    """

    target_class = "apps.accounts.api.authentication.SessionAuthentication"
    name = "sessionAuth"


class SchemaView(SpectacularAPIView):
    """``GET /api/v1/schema/``: signed-in users only.

    drf-spectacular's views default to ``AllowAny``. This view takes its
    authentication and permission classes from DRF's project defaults
    instead, so it can never be more open than any other endpoint.
    """

    authentication_classes = api_settings.DEFAULT_AUTHENTICATION_CLASSES
    permission_classes = api_settings.DEFAULT_PERMISSION_CLASSES

    def handle_exception(self, exc: Exception) -> Response:
        # Errors use the JSON envelope like every other endpoint, not the
        # schema's YAML renderer.
        response = super().handle_exception(exc)
        self.request.accepted_renderer = JSONRenderer()
        self.request.accepted_media_type = JSONRenderer.media_type
        return response


class AllFieldsOptional:
    """Mixin for partial-update serializers: every field may be omitted.

    Used by the view at runtime and by the schema, so the documented PATCH
    body is exactly what the endpoint accepts.
    """

    def get_fields(self) -> dict[str, Any]:
        fields: dict[str, Any] = super().get_fields()  # type: ignore[misc]
        for field in fields.values():
            field.required = False
        return fields


def paginated(serializer: type[serializers.Serializer[Any]], name: str) -> Any:
    """The page shape of ``api.pagination.StandardPagination`` around ``serializer``."""
    return inline_serializer(
        name=f"Paginated{name}List",
        fields={
            "count": serializers.IntegerField(),
            "next": serializers.URLField(allow_null=True),
            "previous": serializers.URLField(allow_null=True),
            "results": serializer(many=True),
        },
    )


#: The envelope every error uses (api.exceptions, API conventions "Errors").
ERROR_ENVELOPE: dict[str, Any] = {
    "type": "object",
    "required": ["error"],
    "properties": {
        "error": {
            "type": "object",
            "required": ["code", "message", "details", "request_id"],
            "properties": {
                "code": {"type": "string", "description": "Stable, machine-readable."},
                "message": {"type": "string", "description": "Safe to show to users."},
                "details": {
                    "nullable": True,
                    "description": "Field-level errors for validation_error; null otherwise.",
                },
                "request_id": {"type": "string"},
            },
        }
    },
}


def add_error_responses(result: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    """Document the error envelope for every operation's 4XX and 5XX answers."""
    result.setdefault("components", {}).setdefault("schemas", {})["ErrorEnvelope"] = ERROR_ENVELOPE
    reference = {
        "description": "An error, in the standard envelope.",
        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorEnvelope"}}},
    }
    for path in result.get("paths", {}).values():
        for operation in path.values():
            responses = operation.setdefault("responses", {})
            responses.setdefault("4XX", reference)
            responses.setdefault("5XX", reference)
    return result
