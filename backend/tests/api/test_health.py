from __future__ import annotations

import logging

import pytest
from django.db import DatabaseError

from apps.core import views
from apps.core.logging import RequestIDFilter

HEALTH_URL = "/api/v1/health/"


@pytest.mark.django_db
def test_health_reports_ok_without_authentication(api_client):
    response = api_client.get(HEALTH_URL)

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"database": "ok"}}
    assert response["Cache-Control"] == "no-store"


class _UnreachableConnection:
    def cursor(self):
        raise DatabaseError("connection refused")


def test_health_reports_unavailable_when_database_is_unreachable(api_client, monkeypatch):
    monkeypatch.setattr(views, "connection", _UnreachableConnection())

    response = api_client.get(HEALTH_URL)

    assert response.status_code == 503
    # Coarse status only: the underlying error text must not leak.
    assert response.json() == {"status": "unavailable", "checks": {"database": "unavailable"}}


@pytest.mark.django_db
def test_every_response_carries_a_generated_request_id(api_client):
    response = api_client.get(HEALTH_URL)

    assert len(response["X-Request-ID"]) == 32


@pytest.mark.django_db
def test_well_formed_incoming_request_id_is_propagated(api_client):
    response = api_client.get(HEALTH_URL, HTTP_X_REQUEST_ID="edge-proxy.123")

    assert response["X-Request-ID"] == "edge-proxy.123"


@pytest.mark.django_db
def test_malformed_incoming_request_id_is_replaced(api_client):
    response = api_client.get(HEALTH_URL, HTTP_X_REQUEST_ID="bad id\nwith newline")

    assert response["X-Request-ID"] != "bad id\nwith newline"
    assert len(response["X-Request-ID"]) == 32


def test_client_error_log_lines_keep_the_request_id(api_client, caplog):
    # Django logs 4xx responses after the middleware has returned, so the
    # filter must recover the ID from the request attached to the record.
    with caplog.at_level(logging.WARNING, logger="django.request"):
        api_client.get("/api/v1/missing/", HTTP_X_REQUEST_ID="trace-404")

    [record] = [r for r in caplog.records if r.name == "django.request"]
    RequestIDFilter().filter(record)
    assert record.request_id == "trace-404"


def test_unknown_api_version_is_not_routed(api_client):
    response = api_client.get("/api/v2/health/")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
