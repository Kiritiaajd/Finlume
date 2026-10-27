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

from uuid import UUID

from django.core.exceptions import PermissionDenied
from django.http import Http404

from apps.accounts.models import User
from apps.organizations.models import OrganizationMembership, OrganizationRole
from apps.workspaces.models import WorkspaceMembership, WorkspaceRole

_WORKSPACE_RANK = {WorkspaceRole.VIEWER: 0, WorkspaceRole.EDITOR: 1, WorkspaceRole.OWNER: 2}
_ORGANIZATION_RANK = {OrganizationRole.MEMBER: 0, OrganizationRole.ADMIN: 1}


def require_workspace_role(
    user: User, workspace_id: UUID, minimum: WorkspaceRole
) -> WorkspaceMembership:
    """Return the caller's membership, with its workspace and organization loaded, or raise."""
    try:
        # One query; the organization join is on its primary key and lets callers
        # render the workspace without a second lookup.
        membership = WorkspaceMembership.objects.select_related("workspace__organization").get(
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
