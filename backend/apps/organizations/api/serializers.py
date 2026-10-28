"""Request and response shapes for organization endpoints."""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers

from apps.organizations.models import Organization, OrganizationMembership, OrganizationRole


class OrganizationNameSerializer(serializers.Serializer[Any]):
    """Create and rename take the same body."""

    name = serializers.CharField(max_length=200)


@extend_schema_serializer(component_name="OrganizationMemberAdd")
class MemberAddSerializer(serializers.Serializer[Any]):
    email = serializers.EmailField(max_length=254)
    role = serializers.ChoiceField(choices=OrganizationRole.choices)


@extend_schema_serializer(component_name="OrganizationMemberRole")
class MemberRoleSerializer(serializers.Serializer[Any]):
    role = serializers.ChoiceField(choices=OrganizationRole.choices)


# --- Responses (for the OpenAPI schema; the views build them below) -------------


class OrganizationSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    name = serializers.CharField()
    my_role = serializers.ChoiceField(choices=OrganizationRole.choices)
    created_at = serializers.DateTimeField()


class OrganizationMemberSerializer(serializers.Serializer[Any]):
    user_id = serializers.UUIDField()
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=OrganizationRole.choices)
    joined_at = serializers.DateTimeField()


def organization_data(organization: Organization, my_role: str) -> dict[str, Any]:
    return {
        "id": organization.public_id,
        "name": organization.name,
        "my_role": my_role,
        "created_at": organization.created_at,
    }


def member_data(membership: OrganizationMembership) -> dict[str, Any]:
    """Expects ``user`` already loaded."""
    return {
        "user_id": membership.user.public_id,
        "email": membership.user.email,
        "role": membership.role,
        "joined_at": membership.created_at,
    }
