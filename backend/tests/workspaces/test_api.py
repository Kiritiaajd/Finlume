"""Workspace and member endpoints: role matrix, isolation, invariants and query budgets."""

from __future__ import annotations

import uuid

import pytest

from apps.audit.models import AuditEvent
from apps.organizations.models import OrganizationMembership, OrganizationRole
from apps.workspaces.models import Workspace, WorkspaceMembership, WorkspaceRole

pytestmark = pytest.mark.django_db

VIEWER, EDITOR, OWNER = WorkspaceRole.VIEWER, WorkspaceRole.EDITOR, WorkspaceRole.OWNER


def detail(ws):
    return f"/api/v1/workspaces/{ws.public_id}/"


def members(ws):
    return f"/api/v1/workspaces/{ws.public_id}/members/"


def member(ws, user):
    return f"/api/v1/workspaces/{ws.public_id}/members/{user.public_id}/"


@pytest.fixture
def workspace(make_workspace):
    return make_workspace()


@pytest.fixture
def owner(workspace):
    return workspace.memberships.get().user


@pytest.fixture
def as_user(api_client):
    def sign_in(user):
        api_client.force_login(user)
        return api_client

    return sign_in


# --- Role matrix ---------------------------------------------------------------

# (method, url builder, body, minimum role that succeeds, success status)
ENDPOINTS = [
    ("get", detail, None, VIEWER, 200),
    ("patch", detail, {"name": "Renamed"}, OWNER, 200),
    ("get", members, None, VIEWER, 200),
    ("post", members, "new-member", OWNER, 201),
]
ROLES = [VIEWER, EDITOR, OWNER]


@pytest.mark.parametrize(("method", "url", "body", "minimum", "ok"), ENDPOINTS)
@pytest.mark.parametrize("role", [None, *ROLES])
def test_role_matrix(
    workspace, add_to_workspace, make_user, as_user, method, url, body, minimum, ok, role
):
    caller = make_user() if role is None else add_to_workspace(workspace, role)
    if body == "new-member":
        body = {"user_id": str(add_to_workspace_org_only(workspace, make_user)), "role": VIEWER}

    response = getattr(as_user(caller), method)(url(workspace), body, format="json")

    if role is None:
        expected = 404  # a non-member never learns the workspace exists
    elif ROLES.index(role) >= ROLES.index(minimum):
        expected = ok
    else:
        expected = 403
    assert response.status_code == expected


def add_to_workspace_org_only(workspace, make_user):
    user = make_user()
    OrganizationMembership.objects.create(
        organization_id=workspace.organization_id, user=user, role=OrganizationRole.MEMBER
    )
    return user.public_id


@pytest.mark.parametrize("url", [detail, members])
def test_anonymous_callers_get_401(api_client, workspace, url):
    assert api_client.get(url(workspace)).status_code == 401


def test_unknown_workspace_ids_are_not_found(as_user, owner):
    response = as_user(owner).get(f"/api/v1/workspaces/{uuid.uuid4()}/")

    assert response.status_code == 404


def test_organization_admins_cannot_open_workspaces_they_are_not_members_of(
    workspace, make_user, as_user
):
    org_admin = make_user()
    OrganizationMembership.objects.create(
        organization_id=workspace.organization_id, user=org_admin, role=OrganizationRole.ADMIN
    )

    assert as_user(org_admin).get(detail(workspace)).status_code == 404


# --- Listing and creating -------------------------------------------------------


def test_listing_shows_only_my_workspaces_with_my_role_in_two_queries(
    workspace, add_to_workspace, make_workspace, as_user, assert_app_queries
):
    me = add_to_workspace(workspace, EDITOR)
    make_workspace()  # someone else's
    client = as_user(me)

    with assert_app_queries(2):  # count + page
        response = client.get("/api/v1/workspaces/")

    body = response.json()
    assert body["count"] == 1
    [item] = body["results"]
    assert item["id"] == str(workspace.public_id)
    assert item["my_role"] == EDITOR
    assert item["kind"] == "organization"
    assert item["organization_id"] == str(workspace.organization.public_id)


def test_creating_a_workspace_makes_the_creator_its_owner(make_organization, make_user, as_user):
    creator = make_user()
    organization = make_organization()
    OrganizationMembership.objects.create(
        organization=organization, user=creator, role=OrganizationRole.MEMBER
    )

    response = as_user(creator).post(
        "/api/v1/workspaces/",
        {"organization_id": str(organization.public_id), "name": "Borrower Assessment 001"},
        format="json",
    )

    assert response.status_code == 201
    assert response.json()["my_role"] == OWNER
    workspace = Workspace.objects.get(public_id=response.json()["id"])
    assert list(workspace.memberships.values_list("user_id", "role")) == [(creator.pk, OWNER)]
    assert AuditEvent.objects.filter(action="workspace.created", workspace=workspace).exists()


def test_only_organization_members_can_create_workspaces_in_it(
    make_organization, make_user, as_user
):
    organization = make_organization()

    response = as_user(make_user()).post(
        "/api/v1/workspaces/",
        {"organization_id": str(organization.public_id), "name": "Nope"},
        format="json",
    )

    assert response.status_code == 404
    assert not Workspace.objects.filter(name="Nope").exists()


def test_workspace_detail_is_one_access_query(workspace, owner, as_user, assert_app_queries):
    client = as_user(owner)

    with assert_app_queries(1):  # membership + workspace + organization, joined
        response = client.get(detail(workspace))

    assert response.json()["my_role"] == OWNER


# --- Members ------------------------------------------------------------------


def test_members_list_costs_one_access_query_plus_the_page(
    workspace, owner, add_to_workspace, as_user, assert_app_queries
):
    add_to_workspace(workspace, VIEWER)
    client = as_user(owner)

    with assert_app_queries(3):  # access + count + page (users joined)
        response = client.get(members(workspace))

    assert response.json()["count"] == 2


def test_owners_add_organization_members(workspace, owner, make_user, as_user):
    newcomer = make_user()
    OrganizationMembership.objects.create(
        organization_id=workspace.organization_id, user=newcomer, role=OrganizationRole.MEMBER
    )

    response = as_user(owner).post(
        members(workspace), {"user_id": str(newcomer.public_id), "role": EDITOR}, format="json"
    )

    assert response.status_code == 201
    assert response.json()["role"] == EDITOR
    assert workspace.memberships.filter(user=newcomer, role=EDITOR).exists()


@pytest.mark.parametrize("case", ["outside the organization", "inactive", "already a member"])
def test_adding_an_ineligible_user_is_a_conflict(
    workspace, owner, make_user, add_to_workspace, as_user, case
):
    if case == "outside the organization":
        target = make_user()
    elif case == "inactive":
        target = make_user(is_active=False)
        OrganizationMembership.objects.create(
            organization_id=workspace.organization_id, user=target, role=OrganizationRole.MEMBER
        )
    else:
        target = add_to_workspace(workspace, VIEWER)

    response = as_user(owner).post(
        members(workspace), {"user_id": str(target.public_id), "role": VIEWER}, format="json"
    )

    assert response.status_code == 409


def test_personal_workspaces_take_no_other_members(make_user, as_user):
    me = make_user()
    personal = Workspace.objects.create(name="Personal", personal_owner=me, created_by=me)
    WorkspaceMembership.objects.create(workspace=personal, user=me, role=OWNER)

    response = as_user(me).post(
        members(personal), {"user_id": str(make_user().public_id), "role": VIEWER}, format="json"
    )

    assert response.status_code == 409


def test_owners_change_roles(workspace, owner, add_to_workspace, as_user):
    target = add_to_workspace(workspace, VIEWER)

    response = as_user(owner).patch(member(workspace, target), {"role": OWNER}, format="json")

    assert response.status_code == 200
    assert workspace.memberships.get(user=target).role == OWNER


def test_the_last_owner_can_neither_be_demoted_nor_leave(workspace, owner, as_user):
    client = as_user(owner)

    assert (
        client.patch(member(workspace, owner), {"role": EDITOR}, format="json").status_code == 409
    )
    assert client.delete(member(workspace, owner)).status_code == 409
    assert workspace.memberships.get(user=owner).role == OWNER


def test_an_owner_can_step_down_once_another_owner_exists(
    workspace, owner, add_to_workspace, as_user
):
    add_to_workspace(workspace, OWNER)

    response = as_user(owner).patch(member(workspace, owner), {"role": VIEWER}, format="json")

    assert response.status_code == 200


def test_members_can_leave_but_not_remove_others(workspace, add_to_workspace, as_user):
    leaver = add_to_workspace(workspace, VIEWER)
    other = add_to_workspace(workspace, VIEWER)
    client = as_user(leaver)

    assert client.delete(member(workspace, other)).status_code == 403
    assert client.delete(member(workspace, leaver)).status_code == 204
    assert not workspace.memberships.filter(user=leaver).exists()
    assert AuditEvent.objects.filter(action="membership.removed", metadata__left=True).exists()


def test_owners_remove_members(workspace, owner, add_to_workspace, as_user):
    target = add_to_workspace(workspace, EDITOR)

    assert as_user(owner).delete(member(workspace, target)).status_code == 204
    assert not workspace.memberships.filter(user=target).exists()


def test_unknown_members_are_not_found(workspace, owner, make_user, as_user):
    response = as_user(owner).delete(member(workspace, make_user()))

    assert response.status_code == 404
