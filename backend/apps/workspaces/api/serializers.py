"""Request and response shapes for workspace endpoints."""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers

from apps.workspaces.models import Workspace, WorkspaceMembership, WorkspaceRole


class WorkspaceCreateSerializer(serializers.Serializer[Any]):
    organization_id = serializers.UUIDField()
    name = serializers.CharField(max_length=200)


class WorkspaceRenameSerializer(serializers.Serializer[Any]):
    name = serializers.CharField(max_length=200)


@extend_schema_serializer(component_name="WorkspaceMemberAdd")
class MemberAddSerializer(serializers.Serializer[Any]):
    user_id = serializers.UUIDField()
    role = serializers.ChoiceField(choices=WorkspaceRole.choices)


@extend_schema_serializer(component_name="WorkspaceMemberRole")
class MemberRoleSerializer(serializers.Serializer[Any]):
    role = serializers.ChoiceField(choices=WorkspaceRole.choices)


# --- Responses (for the OpenAPI schema; the views build them below) -------------


class WorkspaceSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    name = serializers.CharField()
    kind = serializers.ChoiceField(choices=["personal", "organization"])
    organization_id = serializers.UUIDField(allow_null=True)
    my_role = serializers.ChoiceField(choices=WorkspaceRole.choices)
    created_at = serializers.DateTimeField()


class WorkspaceMemberSerializer(serializers.Serializer[Any]):
    user_id = serializers.UUIDField()
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=WorkspaceRole.choices)
    joined_at = serializers.DateTimeField()


def workspace_data(workspace: Workspace, my_role: str) -> dict[str, Any]:
    """Expects ``organization`` already loaded (the access resolver and list query do)."""
    return {
        "id": workspace.public_id,
        "name": workspace.name,
        "kind": "personal" if workspace.is_personal else "organization",
        "organization_id": workspace.organization.public_id if workspace.organization else None,
        "my_role": my_role,
        "created_at": workspace.created_at,
    }


def member_data(membership: WorkspaceMembership) -> dict[str, Any]:
    """Expects ``user`` already loaded."""
    return {
        "user_id": membership.user.public_id,
        "email": membership.user.email,
        "role": membership.role,
        "joined_at": membership.created_at,
    }
