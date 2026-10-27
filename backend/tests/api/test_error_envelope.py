from __future__ import annotations

import pytest
from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import exceptions

from api.exceptions import api_exception_handler
from services.errors import ConflictError


def _handle(exc):
    return api_exception_handler(exc, {"view": None, "request": None})


def test_validation_errors_keep_field_details():
    response = _handle(exceptions.ValidationError({"amount": ["Enter a number."]}))

    assert response.status_code == 400
    error = response.data["error"]
    assert error["code"] == "validation_error"
    assert error["details"] == {"amount": ["Enter a number."]}
    assert "request_id" in error


@pytest.mark.parametrize(
    ("exc", "status", "code"),
    [
        (exceptions.NotAuthenticated(), 401, "not_authenticated"),
        (exceptions.PermissionDenied(), 403, "permission_denied"),
        (exceptions.NotFound(), 404, "not_found"),
        (exceptions.Throttled(wait=5), 429, "throttled"),
        (Http404("internal object lookup detail"), 404, "not_found"),
        (PermissionDenied("internal policy detail"), 403, "permission_denied"),
    ],
)
def test_api_exceptions_use_the_envelope(exc, status, code):
    response = _handle(exc)

    assert response.status_code == status
    assert response.data["error"]["code"] == code
    assert response.data["error"]["details"] is None
    assert "internal" not in response.data["error"]["message"]


def test_conflict_errors_from_use_cases_return_409_with_their_message():
    response = _handle(ConflictError("A workspace must keep at least one owner."))

    assert response.status_code == 409
    assert response.data["error"]["code"] == "conflict"
    assert response.data["error"]["message"] == "A workspace must keep at least one owner."


def test_parse_errors_hide_parser_internals():
    response = _handle(exceptions.ParseError("JSON parse error - Expecting value: line 1 column 1"))

    assert response.status_code == 400
    assert response.data["error"]["code"] == "parse_error"
    assert "Expecting value" not in response.data["error"]["message"]


def test_unexpected_exceptions_propagate_to_django():
    assert _handle(RuntimeError("database password is hunter2")) is None
