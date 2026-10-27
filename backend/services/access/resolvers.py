"""Resolve a caller's workspace or organization role in one indexed query.

Every tenant endpoint, download, export and background job goes through these
functions, so the access rule exists in exactly one place (ADR-0008 §6):

- no membership → ``Http404``, so the resource's existence is not revealed;
- a membership with a lower role than required → ``PermissionDenied`` (403).

Organization membership never grants workspace access. Because organization
and workspace memberships are kept in sync (tenancy plan, invariant I2), a
workspace membership alone proves access, and no organization lookup is
needed per request.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict
from uuid import UUID

from django.core.exceptions import PermissionDenied
from django.db.models import F, QuerySet
from django.http import Http404

from apps.accounts.models import User
from apps.organizations.models import OrganizationMembership, OrganizationRole
from apps.workspaces.models import Workspace, WorkspaceMembership, WorkspaceRole

if TYPE_CHECKING:
    # Type-checking only: django-stubs-ext is a development dependency.
    from django_stubs_ext import WithAnnotations


class _CallerRole(TypedDict):
    my_role: str


_WORKSPACE_RANK = {WorkspaceRole.VIEWER: 0, WorkspaceRole.EDITOR: 1, WorkspaceRole.OWNER: 2}
_ORGANIZATION_RANK = {OrganizationRole.MEMBER: 0, OrganizationRole.ADMIN: 1}


def require_workspace_role(
    user: User, workspace_id: UUID, minimum: WorkspaceRole
) -> WorkspaceMembership:
    """Return the caller's membership, with its workspace loaded, or raise."""
    try:
        membership = WorkspaceMembership.objects.select_related("workspace").get(
            user=user, workspace__public_id=workspace_id
        )
    except WorkspaceMembership.DoesNotExist:
        raise Http404 from None
    if _WORKSPACE_RANK[WorkspaceRole(membership.role)] < _WORKSPACE_RANK[minimum]:
        raise PermissionDenied
    return membership


def require_organization_role(
    user: User, organization_id: UUID, minimum: OrganizationRole
) -> OrganizationMembership:
    """Return the caller's organization membership, with its organization loaded, or raise."""
    try:
        membership = OrganizationMembership.objects.select_related("organization").get(
            user=user, organization__public_id=organization_id
        )
    except OrganizationMembership.DoesNotExist:
        raise Http404 from None
    if _ORGANIZATION_RANK[OrganizationRole(membership.role)] < _ORGANIZATION_RANK[minimum]:
        raise PermissionDenied
    return membership


def workspaces_for(user: User) -> QuerySet[WithAnnotations[Workspace, _CallerRole]]:
    """The workspaces the user is a member of, each annotated with ``my_role``.

    One query. The annotation reuses the join made by the filter, so
    ``my_role`` is the caller's own role in that workspace.
    """
    return Workspace.objects.filter(memberships__user=user).annotate(my_role=F("memberships__role"))
