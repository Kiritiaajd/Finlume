"""Errors raised by use cases and mapped once to the API error envelope."""

from __future__ import annotations


class ConflictError(Exception):
    """The request would break an invariant, such as removing a workspace's last owner.

    ``message`` is shown to the client, so it must be safe and contain no
    financial values. The API answers ``409 conflict``.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
