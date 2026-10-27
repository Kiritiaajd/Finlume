"""Organization and organization-member endpoints."""

from __future__ import annotations

from typing import Any, ClassVar
from uuid import UUID

from rest_framework import status
from rest_framework.permissions import SAFE_METHODS
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import BaseThrottle
from rest_framework.views import APIView

from api.pagination import paginated_response
from api.users import request_user
from apps.organizations.models import Organization, OrganizationMembership, OrganizationRole
from services.access import require_organization_role
from services.organizations import (
    add_member,
    change_member_role,
    create_organization,
    remove_member,
    rename_organization,
)

from .serializers import (
    MemberAddSerializer,
    MemberRoleSerializer,
    OrganizationNameSerializer,
    member_data,
    organization_data,
)
from .throttles import MemberAddThrottle


class OrganizationListView(APIView):
    """The caller's organizations with their role in each; create an organization."""

    def get(self, request: Request, version: str) -> Response:
        memberships = (
            OrganizationMembership.objects.filter(user=request_user(request))
            .select_related("organization")
            .order_by("organization__name", "pk")
        )
        return paginated_response(
            request, self, memberships, lambda m: organization_data(m.organization, m.role)
        )

    def post(self, request: Request, version: str) -> Response:
        serializer = OrganizationNameSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        organization = create_organization(actor=request_user(request), **serializer.validated_data)
        return Response(
            organization_data(organization, OrganizationRole.ADMIN),
            status=status.HTTP_201_CREATED,
        )


class OrganizationScopedView(APIView):
    """Resolves the caller's organization membership once per request.

    Members read; admins write. Organization membership never opens the
    organization's workspaces (ADR-0008).
    """

    read_role: ClassVar[OrganizationRole] = OrganizationRole.MEMBER
    write_role: ClassVar[OrganizationRole] = OrganizationRole.ADMIN

    membership: OrganizationMembership
    organization: Organization

    def required_role(self, method: str) -> OrganizationRole:
        return self.read_role if method in SAFE_METHODS else self.write_role

    def initial(self, request: Request, *args: Any, **kwargs: Any) -> None:
        super().initial(request, *args, **kwargs)  # authentication, throttles
        self.membership = require_organization_role(
            request_user(request),
            kwargs["organization_id"],
            self.required_role(request.method or ""),
        )
        self.organization = self.membership.organization


class OrganizationDetailView(OrganizationScopedView):
    def get(self, request: Request, version: str, organization_id: UUID) -> Response:
        return Response(organization_data(self.organization, self.membership.role))

    def patch(self, request: Request, version: str, organization_id: UUID) -> Response:
        serializer = OrganizationNameSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rename_organization(
            actor=request_user(request),
            organization=self.organization,
            **serializer.validated_data,
        )
        return Response(organization_data(self.organization, self.membership.role))


class MemberListView(OrganizationScopedView):
    def get_throttles(self) -> list[BaseThrottle]:
        throttles = list(super().get_throttles())
        if self.request.method == "POST":
            throttles.append(MemberAddThrottle())
        return throttles

    def get(self, request: Request, version: str, organization_id: UUID) -> Response:
        members = (
            OrganizationMembership.objects.filter(organization=self.organization)
            .select_related("user")
            .order_by("created_at", "pk")
        )
        return paginated_response(request, self, members, member_data)

    def post(self, request: Request, version: str, organization_id: UUID) -> Response:
        serializer = MemberAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = add_member(
            actor=request_user(request),
            organization=self.organization,
            **serializer.validated_data,
        )
        return Response(member_data(membership), status=status.HTTP_201_CREATED)


class MemberDetailView(OrganizationScopedView):
    def required_role(self, method: str) -> OrganizationRole:
        # Changing roles is for admins. Anyone may DELETE themselves (leave);
        # removing someone else is checked by the use case.
        return OrganizationRole.ADMIN if method == "PATCH" else OrganizationRole.MEMBER

    def patch(
        self, request: Request, version: str, organization_id: UUID, user_id: UUID
    ) -> Response:
        serializer = MemberRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = change_member_role(
            actor=request_user(request),
            organization=self.organization,
            user_id=user_id,
            **serializer.validated_data,
        )
        return Response(member_data(membership))

    def delete(
        self, request: Request, version: str, organization_id: UUID, user_id: UUID
    ) -> Response:
        remove_member(
            actor=request_user(request),
            actor_role=OrganizationRole(self.membership.role),
            organization=self.organization,
            user_id=user_id,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
