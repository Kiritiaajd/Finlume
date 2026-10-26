from __future__ import annotations

import logging

from .middleware import REQUEST_ID_META_KEY
from .request_context import get_request_id


class RequestIDFilter(logging.Filter):
    """Attach the current request ID to every log record.

    Records emitted by ``django.request`` carry the request itself and may be
    logged after the request context has ended, so the request wins.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        request = getattr(record, "request", None)
        meta = getattr(request, "META", None)
        from_request = meta.get(REQUEST_ID_META_KEY) if isinstance(meta, dict) else None
        record.request_id = from_request or get_request_id()
        return True
