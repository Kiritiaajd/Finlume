"""Errors raised by use cases and mapped once to the API error envelope."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class ConflictError(Exception):
    """The request would break an invariant, such as removing a workspace's last owner.

    ``message`` is shown to the client, so it must be safe and contain no
    financial values. The API answers ``409 conflict``.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidInput(Exception):
    """Input that a use case found invalid, such as a malformed row in an uploaded file.

    ``details`` maps fields (or rows) to messages, like a serializer's errors.
    The API answers ``400 validation_error`` with ``details`` in the envelope.
    """

    def __init__(self, details: Mapping[str, Any]) -> None:
        super().__init__("The input is invalid.")
        self.details = details
