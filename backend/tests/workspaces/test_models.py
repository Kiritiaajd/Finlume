from __future__ import annotations

import pytest
from django.db import IntegrityError, transaction

from apps.organizations.models import Organization
from apps.workspaces.models import Workspace, WorkspaceMembership, WorkspaceRole

pytestmark = pytest.mark.django_db


def test_personal_and_organization_workspaces_are_both_valid(make_user, make_organization):
    user = make_user()
    personal = Workspace.objects.create(name="Personal", personal_owner=user)
    shared = Workspace.objects.create(name="Shared", organization=make_organization())

    assert personal.is_personal
    assert not shared.is_personal


@pytest.mark.parametrize("links", ["both", "neither"])
def test_a_workspace_has_exactly_one_owner_kind(make_user, make_organization, links):
    fields = (
        {"personal_owner": make_user(), "organization": make_organization()}
        if links == "both"
        else {}
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        Workspace.objects.create(name="Invalid", **fields)


def test_a_user_has_at_most_one_personal_workspace(make_user):
    user = make_user()
    Workspace.objects.create(name="Personal", personal_owner=user)

    with pytest.raises(IntegrityError), transaction.atomic():
        Workspace.objects.create(name="Second", personal_owner=user)


def test_a_user_is_a_member_of_a_workspace_at_most_once(make_workspace):
    workspace = make_workspace()
    owner = workspace.memberships.get().user

    with pytest.raises(IntegrityError), transaction.atomic():
        WorkspaceMembership.objects.create(
            workspace=workspace, user=owner, role=WorkspaceRole.VIEWER
        )


def test_membership_roles_are_checked_by_the_database(make_workspace, make_user):
    with pytest.raises(IntegrityError), transaction.atomic():
        WorkspaceMembership.objects.create(
            workspace=make_workspace(), user=make_user(), role="admin"
        )


def test_deleting_an_organization_deletes_its_workspaces_and_memberships(make_workspace):
    workspace = make_workspace()

    Organization.objects.filter(pk=workspace.organization_id).delete()

    assert not Workspace.objects.filter(pk=workspace.pk).exists()
    assert not WorkspaceMembership.objects.filter(workspace_id=workspace.pk).exists()


def test_deleting_a_user_deletes_their_personal_workspace(make_user):
    user = make_user()
    workspace = Workspace.objects.create(name="Personal", personal_owner=user, created_by=user)

    user.delete()

    assert not Workspace.objects.filter(pk=workspace.pk).exists()
