from __future__ import annotations

import uuid

import pytest
from django.core.exceptions import PermissionDenied
from django.http import Http404

from apps.organizations.models import OrganizationMembership, OrganizationRole
from apps.workspaces.models import WorkspaceMembership, WorkspaceRole
from services.access import require_organization_role, require_workspace_role, workspaces_for

pytestmark = pytest.mark.django_db

ROLES = [WorkspaceRole.VIEWER, WorkspaceRole.EDITOR, WorkspaceRole.OWNER]


@pytest.fixture
def member_with_role(make_workspace, make_user):
    def build(role: WorkspaceRole):
        workspace = make_workspace()
        user = make_user()
        OrganizationMembership.objects.create(
            organization=workspace.organization, user=user, role=OrganizationRole.MEMBER
        )
        WorkspaceMembership.objects.create(workspace=workspace, user=user, role=role)
        return user, workspace

    return build


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("minimum", ROLES)
def test_workspace_role_matrix(member_with_role, role, minimum):
    user, workspace = member_with_role(role)

    if ROLES.index(role) >= ROLES.index(minimum):
        assert require_workspace_role(user, workspace.public_id, minimum).role == role
    else:
        with pytest.raises(PermissionDenied):
            require_workspace_role(user, workspace.public_id, minimum)


def test_access_check_is_one_query_and_loads_the_workspace(
    member_with_role, django_assert_num_queries
):
    user, workspace = member_with_role(WorkspaceRole.EDITOR)

    with django_assert_num_queries(1):
        membership = require_workspace_role(user, workspace.public_id, WorkspaceRole.VIEWER)
        assert membership.workspace.name == workspace.name


def test_non_members_and_unknown_workspaces_are_not_found(make_workspace, make_user):
    workspace = make_workspace()
    outsider = make_user()

    with pytest.raises(Http404):
        require_workspace_role(outsider, workspace.public_id, WorkspaceRole.VIEWER)
    with pytest.raises(Http404):
        require_workspace_role(outsider, uuid.uuid4(), WorkspaceRole.VIEWER)


def test_organization_admins_get_no_access_to_workspaces_they_are_not_members_of(
    make_workspace, make_user
):
    workspace = make_workspace()
    org_admin = make_user()
    OrganizationMembership.objects.create(
        organization=workspace.organization, user=org_admin, role=OrganizationRole.ADMIN
    )

    with pytest.raises(Http404):
        require_workspace_role(org_admin, workspace.public_id, WorkspaceRole.VIEWER)


def test_organization_role_check(make_organization, make_user):
    organization = make_organization()
    admin = organization.memberships.get().user
    member = make_user()
    OrganizationMembership.objects.create(
        organization=organization, user=member, role=OrganizationRole.MEMBER
    )

    assert require_organization_role(admin, organization.public_id, OrganizationRole.ADMIN)
    assert require_organization_role(member, organization.public_id, OrganizationRole.MEMBER)
    with pytest.raises(PermissionDenied):
        require_organization_role(member, organization.public_id, OrganizationRole.ADMIN)
    with pytest.raises(Http404):
        require_organization_role(make_user(), organization.public_id, OrganizationRole.MEMBER)


def test_workspaces_for_lists_only_own_workspaces_with_the_callers_role(
    member_with_role, make_workspace, django_assert_num_queries
):
    user, mine = member_with_role(WorkspaceRole.VIEWER)
    make_workspace()  # someone else's

    with django_assert_num_queries(1):
        rows = [(w.pk, w.my_role) for w in workspaces_for(user)]

    assert rows == [(mine.pk, WorkspaceRole.VIEWER)]
