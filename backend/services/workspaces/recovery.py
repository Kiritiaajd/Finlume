"""Operator-only, audited ownership recovery for workspaces whose owners are all inactive.

There is no API for this: only whoever runs the instance can invoke it
(``manage.py recover_workspace_owner``). Organization admins never gain
access on their own (ADR-0008 §3). Every recovery writes an audit event that
the workspace's members can later see.
"""

from __future__ import annotations

from uuid import UUID

from django.db import transaction
from django.db.models.functions import Lower

from apps.accounts.backends import normalize_email
from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.organizations.models import OrganizationMembership
from apps.workspaces.models import Workspace, WorkspaceMembership, WorkspaceRole
from services.errors import ConflictError


@transaction.atomic
def recover_workspace_owner(
    *, workspace_id: UUID, new_owner_email: str, reason: str, operator: str
) -> AuditEvent:
    """Make one named organization member an owner, if and only if every owner is inactive."""
    reason = reason.strip()
    if not reason:
        raise ConflictError("A reason is required.")

    workspace = Workspace.objects.select_for_update().filter(public_id=workspace_id).first()
    if workspace is None:
        raise ConflictError("No workspace has this ID.")
    if workspace.organization_id is None:
        raise ConflictError("Personal workspaces cannot be recovered to another user.")

    owners = list(
        WorkspaceMembership.objects.filter(workspace=workspace, role=WorkspaceRole.OWNER)
        .select_related("user")
        .order_by("pk")
    )
    if any(owner.user.is_active for owner in owners):
        raise ConflictError(
            "The workspace still has an active owner, who can transfer ownership instead."
        )

    new_owner = (
        User.objects.alias(email_lower=Lower("email"))
        .filter(email_lower=normalize_email(new_owner_email), is_active=True)
        .first()
    )
    if (
        new_owner is None
        or not OrganizationMembership.objects.filter(
            organization_id=workspace.organization_id, user=new_owner
        ).exists()
    ):
        raise ConflictError(
            "The new owner must be an active member of the workspace's organization."
        )

    WorkspaceMembership.objects.update_or_create(
        workspace=workspace, user=new_owner, defaults={"role": WorkspaceRole.OWNER}
    )
    return AuditEvent.record(
        "workspace.ownership_recovered",
        workspace=workspace,
        target=workspace,
        new_owner=str(new_owner.public_id),
        previous_owners=[str(owner.user.public_id) for owner in owners],
        reason=reason,
        operator=operator,
    )
