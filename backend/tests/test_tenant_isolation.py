"""Tenant isolation: the security tests the tenancy plan requires by the end of PR 1d (§8).

Every case runs against every tenancy endpoint it applies to, so a new route
added to these lists is covered by the same rules.
"""

from __future__ import annotations

import pytest

from apps.organizations.models import OrganizationMembership, OrganizationRole
from apps.workspaces.models import Workspace, WorkspaceMembership, WorkspaceRole

pytestmark = pytest.mark.django_db

# (method, path template, body). Templates use {org}, {ws} and {user} public IDs.
ORGANIZATION_ENDPOINTS = [
    ("get", "/api/v1/organizations/{org}/", None),
    ("patch", "/api/v1/organizations/{org}/", {"name": "Taken over"}),
    ("get", "/api/v1/organizations/{org}/members/", None),
    ("post", "/api/v1/organizations/{org}/members/", {"email": "x@example.com", "role": "member"}),
    ("patch", "/api/v1/organizations/{org}/members/{user}/", {"role": "admin"}),
    ("delete", "/api/v1/organizations/{org}/members/{user}/", None),
]
WORKSPACE_ENDPOINTS = [
    ("get", "/api/v1/workspaces/{ws}/", None),
    ("patch", "/api/v1/workspaces/{ws}/", {"name": "Taken over"}),
    ("get", "/api/v1/workspaces/{ws}/members/", None),
    ("post", "/api/v1/workspaces/{ws}/members/", {"user_id": "{user}", "role": "viewer"}),
    ("patch", "/api/v1/workspaces/{ws}/members/{user}/", {"role": "owner"}),
    ("delete", "/api/v1/workspaces/{ws}/members/{user}/", None),
]
COLLECTIONS = [
    ("get", "/api/v1/organizations/", None),
    ("post", "/api/v1/organizations/", {"name": "New"}),
    ("get", "/api/v1/workspaces/", None),
    ("post", "/api/v1/workspaces/", {"organization_id": "{org}", "name": "New"}),
]


def call(client, endpoint, *, org=None, ws=None, user=None):
    method, template, body = endpoint
    ids = {
        "org": org.public_id if org else None,
        "ws": ws.public_id if ws else None,
        "user": user.public_id if user else None,
    }
    if isinstance(body, dict):
        body = {k: v.format(**ids) if isinstance(v, str) else v for k, v in body.items()}
    return getattr(client, method)(template.format(**ids), body, format="json")


@pytest.fixture
def as_user(api_client):
    def sign_in(user):
        api_client.force_login(user)
        return api_client

    return sign_in


@pytest.fixture
def org_b(make_workspace):
    """Organization B with one workspace, its owner (also B's admin) and a second member."""
    workspace = make_workspace()
    return workspace.organization, workspace, workspace.memberships.get().user


def as_org_role(organization, user, role):
    OrganizationMembership.objects.create(organization=organization, user=user, role=role)
    return user


# --- Organization A cannot reach organization B ------------------------------------


@pytest.mark.parametrize("endpoint", ORGANIZATION_ENDPOINTS + WORKSPACE_ENDPOINTS)
@pytest.mark.parametrize("role_in_a", list(OrganizationRole))
def test_a_member_of_another_organization_gets_404_for_everything_in_it(
    make_organization, make_user, org_b, as_user, endpoint, role_in_a
):
    organization, workspace, owner = org_b
    caller = as_org_role(make_organization(), make_user(), role_in_a)

    response = call(as_user(caller), endpoint, org=organization, ws=workspace, user=owner)

    assert response.status_code == 404


def test_another_organization_is_never_listed_and_cannot_take_new_workspaces(
    make_organization, org_b, as_user
):
    organization, _, _ = org_b
    caller = make_organization().memberships.get().user
    client = as_user(caller)

    assert client.get("/api/v1/organizations/").json()["count"] == 1  # only their own
    assert client.get("/api/v1/workspaces/").json()["count"] == 0
    response = client.post(
        "/api/v1/workspaces/",
        {"organization_id": str(organization.public_id), "name": "Planted"},
        format="json",
    )
    assert response.status_code == 404
    assert not Workspace.objects.filter(name="Planted").exists()


# --- Organization roles never open workspaces --------------------------------------


@pytest.mark.parametrize("endpoint", WORKSPACE_ENDPOINTS)
@pytest.mark.parametrize("role", list(OrganizationRole))
def test_organization_members_and_admins_get_404_for_workspaces_they_are_not_in(
    make_user, org_b, as_user, endpoint, role
):
    organization, workspace, owner = org_b
    caller = as_org_role(organization, make_user(), role)

    response = call(as_user(caller), endpoint, org=organization, ws=workspace, user=owner)

    assert response.status_code == 404


# --- Viewers cannot manage a workspace -----------------------------------------------


@pytest.mark.parametrize("endpoint", [e for e in WORKSPACE_ENDPOINTS if e[0] in ("patch", "post")])
def test_viewers_cannot_rename_a_workspace_or_manage_its_members(
    org_b, add_to_workspace, make_user, as_user, endpoint
):
    organization, workspace, owner = org_b
    viewer = add_to_workspace(workspace, WorkspaceRole.VIEWER)
    candidate = as_org_role(organization, make_user(), OrganizationRole.MEMBER)
    target = candidate if endpoint[0] == "post" else owner

    response = call(as_user(viewer), endpoint, org=organization, ws=workspace, user=target)

    assert response.status_code == 403


def test_viewers_cannot_remove_other_members(org_b, add_to_workspace, as_user):
    _, workspace, owner = org_b
    viewer = add_to_workspace(workspace, WorkspaceRole.VIEWER)

    remove = ("delete", "/api/v1/workspaces/{ws}/members/{user}/", None)

    response = call(as_user(viewer), remove, ws=workspace, user=owner)

    assert response.status_code == 403
    assert workspace.memberships.filter(user=owner).exists()


# --- Personal workspaces stay private -------------------------------------------------


@pytest.mark.parametrize("endpoint", WORKSPACE_ENDPOINTS)
def test_another_users_personal_workspace_is_not_found_by_its_id(
    make_user, org_b, as_user, endpoint
):
    _, _, org_admin = org_b
    victim = make_user()
    personal = Workspace.objects.create(name="Personal", personal_owner=victim, created_by=victim)
    WorkspaceMembership.objects.create(workspace=personal, user=victim, role=WorkspaceRole.OWNER)

    response = call(as_user(org_admin), endpoint, ws=personal, user=victim)

    assert response.status_code == 404


# --- Anonymous callers ------------------------------------------------------------


@pytest.mark.parametrize("endpoint", ORGANIZATION_ENDPOINTS + WORKSPACE_ENDPOINTS + COLLECTIONS)
def test_every_tenancy_endpoint_answers_401_to_anonymous_callers(api_client, org_b, endpoint):
    organization, workspace, owner = org_b

    response = call(api_client, endpoint, org=organization, ws=workspace, user=owner)

    assert response.status_code == 401
    assert response["WWW-Authenticate"] == "Session"
