"""WorkspaceScopedView: resolves the workspace once per request and scopes querysets.

Every endpoint under ``/workspaces/{workspace_id}/`` inherits it, in this and
every later module (statements, documents, analyses). Authorization therefore
costs one indexed query per request, and data from another workspace cannot
be loaded at all.
"""

from __future__ import annotations

from typing import Any, ClassVar, TypeVar

from django.db.models import Model, QuerySet
from rest_framework.permissions import SAFE_METHODS
from rest_framework.request import Request
from rest_framework.views import APIView

from api.users import request_user
from apps.workspaces.models import Workspace, WorkspaceMembership, WorkspaceRole
from services.access import require_workspace_role

_M = TypeVar("_M", bound=Model)


class WorkspaceScopedView(APIView):
    """Base view for tenant resources.

    Reads need ``read_role``; writes need ``write_role``. A view overrides
    ``required_role`` for anything finer.
    """

    read_role: ClassVar[WorkspaceRole] = WorkspaceRole.VIEWER
    write_role: ClassVar[WorkspaceRole] = WorkspaceRole.EDITOR

    membership: WorkspaceMembership
    workspace: Workspace

    def required_role(self, method: str) -> WorkspaceRole:
        return self.read_role if method in SAFE_METHODS else self.write_role

    def initial(self, request: Request, *args: Any, **kwargs: Any) -> None:
        super().initial(request, *args, **kwargs)  # authentication, throttles
        self.membership = require_workspace_role(
            request_user(request), kwargs["workspace_id"], self.required_role(request.method or "")
        )
        self.workspace = self.membership.workspace

    def scoped(self, queryset: QuerySet[_M]) -> QuerySet[_M]:
        """Restrict a tenant queryset to this request's workspace."""
        return queryset.filter(workspace=self.workspace)
