"""List pagination shared by every endpoint."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from django.db.models import Model, QuerySet
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


class StandardPagination(PageNumberPagination):
    """Default list pagination: ``?page=N&page_size=M``, capped at 200 items."""

    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200


def paginated_response[M: Model](
    request: Request,
    view: APIView,
    queryset: QuerySet[M],
    represent: Callable[[M], dict[str, Any]],
) -> Response:
    """One page of ``queryset`` in the standard envelope: two queries (count + page).

    ``queryset`` must be ordered, so pages are stable.
    """
    paginator = StandardPagination()
    page = paginator.paginate_queryset(queryset, request, view=view) or []
    return paginator.get_paginated_response([represent(item) for item in page])
