"""The OpenAPI schema: access, the committed contract, validity and completeness (MVP step 6)."""

from __future__ import annotations

import pytest
from django.urls import resolve
from drf_spectacular.drainage import GENERATOR_STATS
from drf_spectacular.generators import SchemaGenerator
from drf_spectacular.renderers import OpenApiYamlRenderer
from drf_spectacular.settings import spectacular_settings
from drf_spectacular.validation import validate_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.settings import api_settings

from .contract import SCHEMA_FILE, contract

SCHEMA_URL = "/api/v1/schema/"


def generate() -> dict:
    return SchemaGenerator(api_version="v1").get_schema(request=None, public=True)


# --- Access is authentication, not just a URL -------------------------------------------


@pytest.mark.django_db
def test_anonymous_callers_get_401_with_the_session_challenge(api_client):
    response = api_client.get(SCHEMA_URL)

    assert response.status_code == 401
    assert response["WWW-Authenticate"] == "Session"
    assert response.json()["error"]["code"] == "not_authenticated"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("query", "content_type"),
    [("", "application/vnd.oai.openapi"), ("?format=json", "application/vnd.oai.openapi+json")],
)
def test_signed_in_users_get_the_schema(api_client, make_user, query, content_type):
    api_client.force_login(make_user())

    response = api_client.get(SCHEMA_URL + query)

    assert response.status_code == 200
    assert content_type in response["Content-Type"]
    assert b"Finlume API" in response.content


def test_the_schema_view_uses_the_project_authentication_and_permissions():
    view = resolve(SCHEMA_URL).func.view_class  # type: ignore[attr-defined]

    assert list(view.authentication_classes) == list(api_settings.DEFAULT_AUTHENTICATION_CLASSES)
    assert list(view.permission_classes) == list(api_settings.DEFAULT_PERMISSION_CLASSES)
    assert IsAuthenticated in view.permission_classes
    assert AllowAny not in view.permission_classes


def test_drf_spectacular_views_are_closed_by_default_too():
    # Its own default is AllowAny; any other drf-spectacular view must not inherit it.
    assert [IsAuthenticated] == spectacular_settings.SERVE_PERMISSIONS


# --- The committed contract --------------------------------------------------------------


def test_the_committed_schema_is_the_generated_schema():
    rendered = OpenApiYamlRenderer().render(generate(), renderer_context={}).decode()
    committed = SCHEMA_FILE.read_text(encoding="utf-8")

    assert rendered.replace("\r\n", "\n") == committed.replace("\r\n", "\n"), (
        "docs/api/openapi-v1.yaml is out of date. Regenerate it with:\n"
        "  python manage.py spectacular --api-version v1 --file ../docs/api/openapi-v1.yaml "
        "--validate --fail-on-warn\n"
        "then regenerate the web client's types (npm run api:types in apps/web)."
    )


def test_the_schema_validates_and_generates_without_warnings():
    GENERATOR_STATS.reset()

    schema = generate()

    validate_schema(schema)
    assert not GENERATOR_STATS, "schema generation emitted warnings or errors"


def test_every_operation_documents_its_success_and_error_responses():
    for path, operations in contract()["paths"].items():
        for method, operation in operations.items():
            responses = operation["responses"]
            successes = [code for code in responses if code.startswith("2")]
            assert successes, f"{method.upper()} {path} documents no success response"
            assert "4XX" in responses, f"{method.upper()} {path} documents no error envelope"
            for code in successes:
                if code != "204":
                    assert "content" in responses[code], (
                        f"{method.upper()} {path} {code} has no body"
                    )


def test_every_operation_has_a_unique_operation_id():
    ids = [
        operation["operationId"]
        for operations in contract()["paths"].values()
        for operation in operations.values()
    ]

    assert len(ids) == len(set(ids))
