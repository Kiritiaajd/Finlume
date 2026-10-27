"""manage.py recover_workspace_owner: operator-only, audited, and refuses every unsafe case."""

from __future__ import annotations

import uuid
from io import StringIO

import pytest
from django.core.management import CommandError, call_command

from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.organizations.models import OrganizationMembership, OrganizationRole
from apps.workspaces.models import Workspace, WorkspaceMembership, WorkspaceRole

pytestmark = pytest.mark.django_db


@pytest.fixture
def orphaned(make_workspace, make_user):
    """A workspace whose only owner is deactivated, and an eligible organization member."""
    workspace = make_workspace()
    old_owner = workspace.memberships.get().user
    User.objects.filter(pk=old_owner.pk).update(is_active=False)
    successor = make_user()
    OrganizationMembership.objects.create(
        organization_id=workspace.organization_id, user=successor, role=OrganizationRole.MEMBER
    )
    return workspace, old_owner, successor


def recover(workspace_id, email, reason="Owner left the company; ticket OPS-42"):
    out = StringIO()
    call_command("recover_workspace_owner", str(workspace_id), email, reason=reason, stdout=out)
    return out.getvalue()


def test_recovery_makes_the_named_member_owner_and_is_audited(orphaned):
    workspace, old_owner, successor = orphaned

    output = recover(workspace.public_id, successor.email.upper())

    assert workspace.memberships.get(user=successor).role == WorkspaceRole.OWNER
    event = AuditEvent.objects.get(action="workspace.ownership_recovered")
    assert str(event.public_id) in output
    assert event.workspace == workspace
    assert event.metadata["new_owner"] == str(successor.public_id)
    assert event.metadata["previous_owners"] == [str(old_owner.public_id)]
    assert event.metadata["reason"] == "Owner left the company; ticket OPS-42"
    assert event.metadata["operator"]


def test_an_existing_member_is_promoted_rather_than_duplicated(orphaned):
    workspace, _, successor = orphaned
    WorkspaceMembership.objects.create(
        workspace=workspace, user=successor, role=WorkspaceRole.VIEWER
    )

    recover(workspace.public_id, successor.email)

    assert workspace.memberships.get(user=successor).role == WorkspaceRole.OWNER


def test_refuses_while_an_owner_is_still_active(orphaned):
    workspace, old_owner, successor = orphaned
    User.objects.filter(pk=old_owner.pk).update(is_active=True)

    with pytest.raises(CommandError, match="active owner"):
        recover(workspace.public_id, successor.email)


def test_refuses_people_outside_the_organization(orphaned, make_user):
    workspace, _, _ = orphaned

    with pytest.raises(CommandError, match="active member"):
        recover(workspace.public_id, make_user().email)


def test_refuses_inactive_successors(orphaned):
    workspace, _, successor = orphaned
    User.objects.filter(pk=successor.pk).update(is_active=False)

    with pytest.raises(CommandError, match="active member"):
        recover(workspace.public_id, successor.email)


def test_refuses_personal_workspaces(make_user):
    me = make_user(is_active=False)
    personal = Workspace.objects.create(name="Personal", personal_owner=me, created_by=me)

    with pytest.raises(CommandError, match="Personal"):
        recover(personal.public_id, make_user().email)


def test_refuses_a_blank_reason_and_unknown_workspaces(orphaned):
    workspace, _, successor = orphaned

    with pytest.raises(CommandError, match="reason"):
        recover(workspace.public_id, successor.email, reason="   ")
    with pytest.raises(CommandError, match="No workspace"):
        recover(uuid.uuid4(), successor.email)
    assert not AuditEvent.objects.exists()
