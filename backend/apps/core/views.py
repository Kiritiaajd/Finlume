from __future__ import annotations

import logging

from django.db import DatabaseError, connection
from django.http import HttpRequest, JsonResponse
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .exceptions import error_body

logger = logging.getLogger(__name__)


class HealthView(APIView):
    """Readiness probe: is the application up and can it reach its database?

    Public and unthrottled so load balancers and uptime monitors can poll it.
    It reports only coarse status, never versions, hosts or error text.
    """

    authentication_classes = ()
    permission_classes = (AllowAny,)
    throttle_classes = ()

    def get(self, request: Request, version: str) -> Response:
        database_ok = _database_is_reachable()
        body = {
            "status": "ok" if database_ok else "unavailable",
            "checks": {"database": "ok" if database_ok else "unavailable"},
        }
        http_status = status.HTTP_200_OK if database_ok else status.HTTP_503_SERVICE_UNAVAILABLE
        return Response(body, status=http_status, headers={"Cache-Control": "no-store"})


def _database_is_reachable() -> bool:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        logger.exception("Health check could not reach the database.")
        return False
    return True


def not_found(request: HttpRequest, exception: Exception) -> JsonResponse:
    return JsonResponse(
        error_body("not_found", "The requested resource was not found."),
        status=status.HTTP_404_NOT_FOUND,
    )


def server_error(request: HttpRequest) -> JsonResponse:
    return JsonResponse(
        error_body("server_error", "An unexpected error occurred."),
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
