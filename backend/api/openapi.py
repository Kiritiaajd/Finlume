"""The schema class behind every view (``DEFAULT_SCHEMA_CLASS``).

Kept apart from ``api.schema``: drf-spectacular's views resolve this setting
when they are imported, so this module must not import them.
"""

from __future__ import annotations

import re

from drf_spectacular.openapi import AutoSchema


class FinlumeAutoSchema(AutoSchema):
    """Operation IDs from the app, view and method, e.g. ``organizations_member_list_get``.

    The default derives them from the path and calls list and detail reads
    both "retrieve". These are unique and stable, and generated client types
    are named after them.
    """

    def get_operation_id(self) -> str:
        view = type(self.view)
        app = view.__module__.split(".")[1]  # apps.<app>.api.views
        name = re.sub(r"(?<!^)(?=[A-Z])", "_", view.__name__.removesuffix("View")).lower()
        return f"{app}_{name}_{self.method.lower()}"
