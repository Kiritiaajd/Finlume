"""Request and response shapes for organization endpoints."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.organizations.models import Organization, OrganizationMembership, OrganizationRole


class OrganizationNameSerializer(serializers.Serializer[Any]):
    """Create and rename take the same body."""

    name = serializers.CharField(max_length=200)


class MemberAddSerializer(serializers.Serializer[Any]):
    email = serializers.EmailField(max_length=254)
    role = serializers.ChoiceField(choices=OrganizationRole.choices)


class MemberRoleSerializer(serializers.Serializer[Any]):
    role = serializers.ChoiceField(choices=OrganizationRole.choices)


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
