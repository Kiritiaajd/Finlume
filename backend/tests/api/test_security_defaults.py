"""Project-wide DRF defaults, exercised through views that set no policy of their own."""

from __future__ import annotations

import pytest
from django.urls import re_path
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.serializers import Serializer
from rest_framework.test import APIClient
from rest_framework.views import APIView

from apps.accounts.models import User


class DefaultPolicyView(APIView):
    def get(self, request, version):
        return Response({"ok": True})

    def post(self, request, version):
        return Response({"ok": True})


class _NumberSerializer(Serializer):
    def to_representation(self, instance):
        return instance


class DefaultPaginationView(ListAPIView):
    serializer_class = _NumberSerializer

    def get_queryset(self):
        return list(range(500))


urlpatterns = [
    re_path(r"^api/(?P<version>v1)/default-policy/$", DefaultPolicyView.as_view()),
    re_path(r"^api/(?P<version>v1)/default-pagination/$", DefaultPaginationView.as_view()),
]

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.urls(__name__),
]


@pytest.fixture
def user():
    return User.objects.create_user("analyst", email="analyst@example.com", password="x" * 16)


def test_anonymous_requests_are_rejected_by_default(api_client):
    response = api_client.get("/api/v1/default-policy/")

    # The Session challenge makes DRF answer 401 rather than 403 (ADR-0007).
    assert response.status_code == 401
    assert response["WWW-Authenticate"] == "Session"
    assert response.json()["error"]["code"] == "not_authenticated"


def test_authenticated_requests_are_allowed(api_client, user):
    api_client.force_login(user)

    assert api_client.get("/api/v1/default-policy/").status_code == 200


def test_session_writes_require_a_csrf_token(user):
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(user)

    response = client.post("/api/v1/default-policy/", {}, format="json")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "permission_denied"


def test_lists_are_paginated_with_a_capped_page_size(api_client, user):
    api_client.force_login(user)

    default_page = api_client.get("/api/v1/default-pagination/").json()
    oversized_page = api_client.get("/api/v1/default-pagination/?page_size=1000").json()

    assert default_page["count"] == 500
    assert len(default_page["results"]) == 50
    assert len(oversized_page["results"]) == 200
