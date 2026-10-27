"""Create and rename organization workspaces."""

from __future__ import annotations

from uuid import UUID

from django.db import transaction

from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.organizations.models import OrganizationRole
from apps.workspaces.models import Workspace, WorkspaceMembership, WorkspaceRole
from services.access import require_organization_role


@transaction.atomic
def create_workspace(*, actor: User, organization_id: UUID, name: str) -> Workspace:
    """Create a workspace in an organization the actor belongs to.

    The creator becomes its owner in the same transaction (invariant I5).
    A caller outside the organization gets ``Http404``.
    """
    organization = require_organization_role(
        actor, organization_id, OrganizationRole.MEMBER
    ).organization
    workspace = Workspace.objects.create(name=name, organization=organization, created_by=actor)
    WorkspaceMembership.objects.create(workspace=workspace, user=actor, role=WorkspaceRole.OWNER)
    AuditEvent.record("workspace.created", actor=actor, workspace=workspace, target=workspace)
    return workspace


def rename_workspace(*, actor: User, workspace: Workspace, name: str) -> Workspace:
    workspace.name = name
    workspace.save(update_fields=["name", "updated_at"])
    AuditEvent.record("workspace.renamed", actor=actor, workspace=workspace, target=workspace)
    return workspace
