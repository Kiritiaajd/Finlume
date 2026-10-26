"""Per-request context that must be reachable from logging and error handlers."""

from __future__ import annotations

from contextvars import ContextVar, Token

NO_REQUEST_ID = "-"

_request_id: ContextVar[str] = ContextVar("finlume_request_id", default=NO_REQUEST_ID)


def get_request_id() -> str:
    return _request_id.get()


def set_request_id(request_id: str) -> Token[str]:
    return _request_id.set(request_id)


def reset_request_id(token: Token[str]) -> None:
    _request_id.reset(token)
