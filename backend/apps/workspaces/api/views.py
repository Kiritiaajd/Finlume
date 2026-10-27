"""Workspace and workspace-member endpoints."""

from __future__ import annotations

from uuid import UUID

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api.pagination import paginated_response
from api.users import request_user
from apps.workspaces.models import WorkspaceMembership, WorkspaceRole
from services.workspaces import (
    add_member,
    change_member_role,
    create_workspace,
    remove_member,
    rename_workspace,
)

from .scoping import WorkspaceScopedView
from .serializers import (
    MemberAddSerializer,
    MemberRoleSerializer,
    WorkspaceCreateSerializer,
    WorkspaceRenameSerializer,
    member_data,
    workspace_data,
)


class WorkspaceListView(APIView):
    """The caller's workspaces with their role in each; create an organization workspace."""

    def get(self, request: Request, version: str) -> Response:
        # The caller's memberships carry their role; one query (plus the count).
        memberships = (
            WorkspaceMembership.objects.filter(user=request_user(request))
            .select_related("workspace__organization")
            .order_by("workspace__name", "pk")
        )
        return paginated_response(
            request, self, memberships, lambda m: workspace_data(m.workspace, m.role)
        )

    def post(self, request: Request, version: str) -> Response:
        serializer = WorkspaceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        workspace = create_workspace(actor=request_user(request), **serializer.validated_data)
        return Response(
            workspace_data(workspace, WorkspaceRole.OWNER), status=status.HTTP_201_CREATED
        )


class WorkspaceDetailView(WorkspaceScopedView):
    write_role = WorkspaceRole.OWNER

    def get(self, request: Request, version: str, workspace_id: UUID) -> Response:
        return Response(workspace_data(self.workspace, self.membership.role))

    def patch(self, request: Request, version: str, workspace_id: UUID) -> Response:
        serializer = WorkspaceRenameSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rename_workspace(
            actor=request_user(request), workspace=self.workspace, **serializer.validated_data
        )
        return Response(workspace_data(self.workspace, self.membership.role))


class MemberListView(WorkspaceScopedView):
    write_role = WorkspaceRole.OWNER

    def get(self, request: Request, version: str, workspace_id: UUID) -> Response:
        members = self.scoped(WorkspaceMembership.objects.select_related("user")).order_by(
            "created_at", "pk"
        )
        return paginated_response(request, self, members, member_data)

    def post(self, request: Request, version: str, workspace_id: UUID) -> Response:
        serializer = MemberAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = add_member(
            actor=request_user(request), workspace=self.workspace, **serializer.validated_data
        )
        return Response(member_data(membership), status=status.HTTP_201_CREATED)


class MemberDetailView(WorkspaceScopedView):
    def required_role(self, method: str) -> WorkspaceRole:
        # Changing roles is for owners. Anyone may DELETE themselves (leave);
        # removing someone else is checked by the use case.
        return WorkspaceRole.OWNER if method == "PATCH" else WorkspaceRole.VIEWER

    def patch(self, request: Request, version: str, workspace_id: UUID, user_id: UUID) -> Response:
        serializer = MemberRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = change_member_role(
            actor=request_user(request),
            workspace=self.workspace,
            user_id=user_id,
            **serializer.validated_data,
        )
        return Response(member_data(membership))

    def delete(self, request: Request, version: str, workspace_id: UUID, user_id: UUID) -> Response:
        remove_member(
            actor=request_user(request),
            actor_role=WorkspaceRole(self.membership.role),
            workspace=self.workspace,
            user_id=user_id,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
