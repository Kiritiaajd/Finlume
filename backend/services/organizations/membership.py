"""Add, change and remove organization members, keeping workspace memberships in sync.

Role changes and removals lock the organization row first, so two concurrent
requests cannot both demote or remove "the other" admin (invariant I4). The
lock is ``FOR NO KEY UPDATE``, so it does not block inserts that reference the
organization, such as a new workspace.

Removing a member also removes their memberships in the organization's
workspaces, in the same transaction (invariant I2). It is refused while they
are the last owner of one of those workspaces (I3).
"""

from __future__ import annotations

from uuid import UUID

from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.db.models.functions import Lower
from django.http import Http404

from apps.accounts.backends import normalize_email
from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.organizations.models import Organization, OrganizationMembership, OrganizationRole
from apps.workspaces.models import Workspace, WorkspaceMembership, WorkspaceRole
from services.errors import ConflictError


@transaction.atomic
def add_member(
    *, actor: User, organization: Organization, email: str, role: OrganizationRole
) -> OrganizationMembership:
    """Add an existing, active account by email (invariant I6).

    This reveals whether an address is registered, so the endpoint is
    admin-only and throttled. Invitations by email replace it later.
    """
    user = (
        User.objects.alias(email_lower=Lower("email"))
        .filter(email_lower=normalize_email(email), is_active=True)
        .first()
    )
    if user is None:
        raise ConflictError("No active account uses this email address.")
    try:
        with transaction.atomic():
            membership = OrganizationMembership.objects.create(
                organization=organization, user=user, role=role
            )
    except IntegrityError:
        raise ConflictError("This user is already a member of the organization.") from None
    AuditEvent.record(
        "organization.member_added",
        actor=actor,
        target=user,
        organization=str(organization.public_id),
        role=str(role),
    )
    return membership


@transaction.atomic
def change_member_role(
    *, actor: User, organization: Organization, user_id: UUID, role: OrganizationRole
) -> OrganizationMembership:
    membership = _locked_member(organization, user_id)
    if membership.role == OrganizationRole.ADMIN and role != OrganizationRole.ADMIN:
        _ensure_another_admin(membership)
    previous = membership.role
    membership.role = role
    membership.save(update_fields=["role", "updated_at"])
    AuditEvent.record(
        "organization.member_role_changed",
        actor=actor,
        target=membership.user,
        organization=str(organization.public_id),
        previous_role=previous,
        role=str(role),
    )
    return membership


@transaction.atomic
def remove_member(
    *, actor: User, actor_role: OrganizationRole, organization: Organization, user_id: UUID
) -> None:
    """Admins remove anyone; every member may remove themselves (leave)."""
    membership = _locked_member(organization, user_id)
    leaving = membership.user_id == actor.pk
    if not leaving and actor_role != OrganizationRole.ADMIN:
        raise PermissionDenied
    if membership.role == OrganizationRole.ADMIN:
        _ensure_another_admin(membership)
    _ensure_not_last_workspace_owner(membership)
    removed_workspace_memberships, _ = WorkspaceMembership.objects.filter(
        user_id=membership.user_id, workspace__organization=organization
    ).delete()
    membership.delete()
    AuditEvent.record(
        "organization.member_removed",
        actor=actor,
        target=membership.user,
        organization=str(organization.public_id),
        left=leaving,
        workspace_memberships_removed=removed_workspace_memberships,
    )


def _locked_member(organization: Organization, user_id: UUID) -> OrganizationMembership:
    """Lock the organization row, then load and lock the member. Unknown member → 404.

    Locking the membership row makes adding the user to a workspace, or their
    creating one, wait for a concurrent removal, so I2 holds.
    """
    Organization.objects.select_for_update(no_key=True).only("pk").get(pk=organization.pk)
    try:
        return (
            OrganizationMembership.objects.select_for_update(of=("self",))
            .select_related("user")
            .get(organization=organization, user__public_id=user_id)
        )
    except OrganizationMembership.DoesNotExist:
        raise Http404 from None


def _ensure_another_admin(membership: OrganizationMembership) -> None:
    """Invariant I4."""
    others = OrganizationMembership.objects.filter(
        organization_id=membership.organization_id, role=OrganizationRole.ADMIN
    ).exclude(pk=membership.pk)
    if not others.exists():
        raise ConflictError(
            "An organization must keep at least one admin. Make another member an admin first."
        )


def _ensure_not_last_workspace_owner(membership: OrganizationMembership) -> None:
    """Refuse removal while the member is the only owner of a workspace here (I2, I3).

    The workspaces they own are locked first, in the same order as workspace
    role changes, so no other owner can step down in the meantime.
    """
    owned = list(
        Workspace.objects.select_for_update(of=("self",))
        .filter(
            organization_id=membership.organization_id,
            memberships__user_id=membership.user_id,
            memberships__role=WorkspaceRole.OWNER,
        )
        .order_by("pk")
        .values_list("pk", flat=True)
    )
    if not owned:
        return
    sole_owner = (
        Workspace.objects.filter(pk__in=owned)
        .annotate(owners=Count("memberships", filter=Q(memberships__role=WorkspaceRole.OWNER)))
        .filter(owners=1)
    )
    if sole_owner.exists():
        # Workspace names stay out of the message: an organization admin may
        # not be a member of those workspaces.
        raise ConflictError(
            "This member is the last owner of a workspace in the organization. "
            "Ownership must be transferred before they can leave the organization."
        )
