"""Add, change and remove workspace members; a workspace always keeps an owner.

Role changes and removals lock the workspace row first, so two concurrent
requests cannot both demote or remove "the other" owner (invariant I3).
"""

from __future__ import annotations

from uuid import UUID

from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.http import Http404

from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.organizations.models import OrganizationMembership
from apps.workspaces.models import Workspace, WorkspaceMembership, WorkspaceRole
from services.errors import ConflictError


@transaction.atomic
def add_member(
    *, actor: User, workspace: Workspace, user_id: UUID, role: WorkspaceRole
) -> WorkspaceMembership:
    """Add an active member of the workspace's organization (invariants I2, I6)."""
    if workspace.organization_id is None:
        raise ConflictError("A personal workspace cannot have other members.")
    try:
        user = (
            OrganizationMembership.objects.select_related("user")
            .get(
                organization_id=workspace.organization_id,
                user__public_id=user_id,
                user__is_active=True,
            )
            .user
        )
    except OrganizationMembership.DoesNotExist:
        raise ConflictError(
            "Only active members of the workspace's organization can be added."
        ) from None
    try:
        with transaction.atomic():
            membership = WorkspaceMembership.objects.create(
                workspace=workspace, user=user, role=role
            )
    except IntegrityError:
        raise ConflictError("This user is already a member of the workspace.") from None
    AuditEvent.record(
        "membership.added", actor=actor, workspace=workspace, target=user, role=str(role)
    )
    return membership


@transaction.atomic
def change_member_role(
    *, actor: User, workspace: Workspace, user_id: UUID, role: WorkspaceRole
) -> WorkspaceMembership:
    membership = _locked_member(workspace, user_id)
    if membership.role == WorkspaceRole.OWNER and role != WorkspaceRole.OWNER:
        _ensure_another_owner(membership)
    previous = membership.role
    membership.role = role
    membership.save(update_fields=["role", "updated_at"])
    AuditEvent.record(
        "membership.role_changed",
        actor=actor,
        workspace=workspace,
        target=membership.user,
        previous_role=previous,
        role=str(role),
    )
    return membership


@transaction.atomic
def remove_member(
    *, actor: User, actor_role: WorkspaceRole, workspace: Workspace, user_id: UUID
) -> None:
    """Owners remove anyone; every member may remove themselves (leave)."""
    membership = _locked_member(workspace, user_id)
    leaving = membership.user_id == actor.pk
    if not leaving and actor_role != WorkspaceRole.OWNER:
        raise PermissionDenied
    if membership.role == WorkspaceRole.OWNER:
        _ensure_another_owner(membership)
    membership.delete()
    AuditEvent.record(
        "membership.removed", actor=actor, workspace=workspace, target=membership.user, left=leaving
    )


def _locked_member(workspace: Workspace, user_id: UUID) -> WorkspaceMembership:
    """Lock the workspace row, then load the member. Unknown member → 404."""
    Workspace.objects.select_for_update().only("pk").get(pk=workspace.pk)
    try:
        return WorkspaceMembership.objects.select_related("user").get(
            workspace=workspace, user__public_id=user_id
        )
    except WorkspaceMembership.DoesNotExist:
        raise Http404 from None


def _ensure_another_owner(membership: WorkspaceMembership) -> None:
    """Invariant I3. Also keeps a personal workspace's only owner in place (I1)."""
    others = WorkspaceMembership.objects.filter(
        workspace_id=membership.workspace_id, role=WorkspaceRole.OWNER
    ).exclude(pk=membership.pk)
    if not others.exists():
        raise ConflictError(
            "A workspace must keep at least one owner. Make another member an owner first."
        )
