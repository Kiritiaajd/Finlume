"""Organization and member endpoints: role matrix, invariants, sync and query budgets."""

from __future__ import annotations

import pytest

from apps.audit.models import AuditEvent
from apps.organizations.api.throttles import MemberAddThrottle
from apps.organizations.models import Organization, OrganizationMembership, OrganizationRole
from apps.workspaces.models import WorkspaceMembership, WorkspaceRole

pytestmark = pytest.mark.django_db

MEMBER, ADMIN = OrganizationRole.MEMBER, OrganizationRole.ADMIN


def detail(org):
    return f"/api/v1/organizations/{org.public_id}/"


def members(org):
    return f"/api/v1/organizations/{org.public_id}/members/"


def member(org, user):
    return f"/api/v1/organizations/{org.public_id}/members/{user.public_id}/"


@pytest.fixture
def organization(make_organization):
    return make_organization()


@pytest.fixture
def admin(organization):
    return organization.memberships.get().user


@pytest.fixture
def add_to_organization(make_user):
    def build(organization, role=MEMBER, user=None):
        user = user or make_user()
        OrganizationMembership.objects.create(organization=organization, user=user, role=role)
        return user

    return build


@pytest.fixture
def as_user(api_client):
    def sign_in(user):
        api_client.force_login(user)
        return api_client

    return sign_in


# --- Role matrix ---------------------------------------------------------------

# (method, url builder, body, minimum role that succeeds, success status)
ENDPOINTS = [
    ("get", detail, None, MEMBER, 200),
    ("patch", detail, {"name": "Renamed"}, ADMIN, 200),
    ("get", members, None, MEMBER, 200),
    ("post", members, "new-member", ADMIN, 201),
    ("patch", "other-member", {"role": ADMIN}, ADMIN, 200),
    ("delete", "other-member", None, ADMIN, 204),
]
ROLES = [MEMBER, ADMIN]


@pytest.mark.parametrize(("method", "url", "body", "minimum", "ok"), ENDPOINTS)
@pytest.mark.parametrize("role", [None, *ROLES])
def test_role_matrix(
    organization, add_to_organization, make_user, as_user, method, url, body, minimum, ok, role
):
    caller = make_user() if role is None else add_to_organization(organization, role)
    if url == "other-member":
        other = add_to_organization(organization)
        url = lambda org: member(org, other)  # noqa: E731
    if body == "new-member":
        body = {"email": make_user().email, "role": MEMBER}

    response = getattr(as_user(caller), method)(url(organization), body, format="json")

    if role is None:
        expected = 404  # a non-member never learns the organization exists
    elif ROLES.index(role) >= ROLES.index(minimum):
        expected = ok
    else:
        expected = 403
    assert response.status_code == expected


# --- Listing, creating, renaming --------------------------------------------------


def test_any_signed_in_user_can_create_an_organization_and_becomes_its_admin(make_user, as_user):
    creator = make_user()

    response = as_user(creator).post(
        "/api/v1/organizations/", {"name": "Example Lending Co"}, format="json"
    )

    assert response.status_code == 201
    body = response.json()
    assert body["my_role"] == ADMIN
    organization = Organization.objects.get(public_id=body["id"])
    assert list(organization.memberships.values_list("user_id", "role")) == [(creator.pk, ADMIN)]
    assert AuditEvent.objects.filter(
        action="organization.created", target_public_id=organization.public_id
    ).exists()


def test_listing_shows_only_my_organizations_with_my_role_in_two_queries(
    organization, add_to_organization, make_organization, as_user, assert_app_queries
):
    me = add_to_organization(organization)
    make_organization()  # someone else's
    client = as_user(me)

    with assert_app_queries(2):  # count + page
        response = client.get("/api/v1/organizations/")

    body = response.json()
    assert body["count"] == 1
    [item] = body["results"]
    assert item["id"] == str(organization.public_id)
    assert item["my_role"] == MEMBER


def test_organization_detail_is_one_access_query(organization, admin, as_user, assert_app_queries):
    client = as_user(admin)

    with assert_app_queries(1):  # membership + organization, joined
        response = client.get(detail(organization))

    assert response.json() == {
        "id": str(organization.public_id),
        "name": organization.name,
        "my_role": ADMIN,
        "created_at": response.json()["created_at"],
    }


def test_admins_rename_the_organization(organization, admin, as_user):
    response = as_user(admin).patch(detail(organization), {"name": "Renamed"}, format="json")

    assert response.status_code == 200
    organization.refresh_from_db()
    assert organization.name == "Renamed"
    assert AuditEvent.objects.filter(action="organization.renamed").exists()


# --- Members ------------------------------------------------------------------


def test_members_list_costs_one_access_query_plus_the_page(
    organization, admin, add_to_organization, as_user, assert_app_queries
):
    add_to_organization(organization)
    client = as_user(admin)

    with assert_app_queries(3):  # access + count + page (users joined)
        response = client.get(members(organization))

    assert response.json()["count"] == 2


def test_admins_add_existing_accounts_by_email_in_any_case(organization, admin, make_user, as_user):
    newcomer = make_user()

    response = as_user(admin).post(
        members(organization), {"email": newcomer.email.upper(), "role": MEMBER}, format="json"
    )

    assert response.status_code == 201
    assert response.json()["user_id"] == str(newcomer.public_id)
    assert organization.memberships.filter(user=newcomer, role=MEMBER).exists()
    assert AuditEvent.objects.filter(
        action="organization.member_added", target_public_id=newcomer.public_id
    ).exists()


@pytest.mark.parametrize("case", ["unknown", "inactive", "already a member"])
def test_adding_an_ineligible_account_is_a_conflict(
    organization, admin, make_user, add_to_organization, as_user, case
):
    if case == "unknown":
        email = "nobody@example.com"
    elif case == "inactive":
        email = make_user(is_active=False).email
    else:
        email = add_to_organization(organization).email

    response = as_user(admin).post(
        members(organization), {"email": email, "role": MEMBER}, format="json"
    )

    assert response.status_code == 409


def test_adding_members_by_email_is_throttled_per_user(
    organization, admin, make_user, as_user, monkeypatch
):
    monkeypatch.setattr(MemberAddThrottle, "rate", "2/hour", raising=False)
    client = as_user(admin)

    def add():
        return client.post(
            members(organization), {"email": make_user().email, "role": MEMBER}, format="json"
        )

    assert [add().status_code for _ in range(3)] == [201, 201, 429]
    assert client.get(members(organization)).status_code == 200  # reads are not limited


def test_admins_change_roles(organization, admin, add_to_organization, as_user):
    target = add_to_organization(organization)

    response = as_user(admin).patch(member(organization, target), {"role": ADMIN}, format="json")

    assert response.status_code == 200
    assert organization.memberships.get(user=target).role == ADMIN


def test_the_last_admin_can_neither_be_demoted_nor_leave(organization, admin, as_user):
    client = as_user(admin)

    assert (
        client.patch(member(organization, admin), {"role": MEMBER}, format="json").status_code
        == 409
    )
    assert client.delete(member(organization, admin)).status_code == 409
    assert organization.memberships.get(user=admin).role == ADMIN


def test_an_admin_can_step_down_once_another_admin_exists(
    organization, admin, add_to_organization, as_user
):
    add_to_organization(organization, ADMIN)

    response = as_user(admin).patch(member(organization, admin), {"role": MEMBER}, format="json")

    assert response.status_code == 200


def test_members_can_leave_but_not_remove_others(organization, add_to_organization, as_user):
    leaver = add_to_organization(organization)
    other = add_to_organization(organization)
    client = as_user(leaver)

    assert client.delete(member(organization, other)).status_code == 403
    assert client.delete(member(organization, leaver)).status_code == 204
    assert not organization.memberships.filter(user=leaver).exists()
    assert AuditEvent.objects.filter(
        action="organization.member_removed", metadata__left=True
    ).exists()


def test_unknown_members_are_not_found(organization, admin, make_user, as_user):
    response = as_user(admin).delete(member(organization, make_user()))

    assert response.status_code == 404


# --- Workspace membership sync (invariant I2) --------------------------------------


def test_removing_a_member_removes_their_workspace_memberships_in_that_organization_only(
    organization, admin, make_workspace, add_to_workspace, make_user, as_user
):
    target = make_user()
    here = [make_workspace(organization=organization, owner=admin) for _ in range(2)]
    for workspace in here:
        add_to_workspace(workspace, WorkspaceRole.EDITOR, user=target)
    elsewhere = make_workspace()
    add_to_workspace(elsewhere, WorkspaceRole.VIEWER, user=target)

    response = as_user(admin).delete(member(organization, target))

    assert response.status_code == 204
    assert list(
        WorkspaceMembership.objects.filter(user=target).values_list("workspace", flat=True)
    ) == [elsewhere.pk]
    event = AuditEvent.objects.get(action="organization.member_removed")
    assert event.metadata["workspace_memberships_removed"] == 2


def test_the_last_owner_of_a_workspace_cannot_be_removed_from_the_organization(
    organization, admin, make_workspace, add_to_organization, as_user
):
    owner = add_to_organization(organization)
    workspace = make_workspace(organization=organization, owner=owner)

    assert as_user(admin).delete(member(organization, owner)).status_code == 409
    assert as_user(owner).delete(member(organization, owner)).status_code == 409
    assert organization.memberships.filter(user=owner).exists()
    assert workspace.memberships.filter(user=owner, role=WorkspaceRole.OWNER).exists()


def test_a_workspace_owner_can_leave_once_another_owner_exists(
    organization, make_workspace, add_to_organization, add_to_workspace, as_user
):
    owner = add_to_organization(organization)
    workspace = make_workspace(organization=organization, owner=owner)
    add_to_workspace(workspace, WorkspaceRole.OWNER)

    assert as_user(owner).delete(member(organization, owner)).status_code == 204
    assert not workspace.memberships.filter(user=owner).exists()
