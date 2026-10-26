from __future__ import annotations

import re
import uuid
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from .request_context import reset_request_id, set_request_id

REQUEST_ID_HEADER = "X-Request-ID"
#: Also stored on the request, because Django logs 4xx responses
#: (``django.request``) after this middleware has returned.
REQUEST_ID_META_KEY = "FINLUME_REQUEST_ID"

# Accept a caller-supplied ID (e.g. from a reverse proxy) only when it is
# short and plain, so it cannot be used to inject content into log lines.
_VALID_REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{1,64}")


class RequestIDMiddleware:
    """Assign every request an ID, expose it in logs and the response header."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        incoming = request.headers.get(REQUEST_ID_HEADER, "")
        request_id = incoming if _VALID_REQUEST_ID.fullmatch(incoming) else uuid.uuid4().hex
        request.META[REQUEST_ID_META_KEY] = request_id
        token = set_request_id(request_id)
        try:
            response = self.get_response(request)
        finally:
            reset_request_id(token)
        response[REQUEST_ID_HEADER] = request_id
        return response
