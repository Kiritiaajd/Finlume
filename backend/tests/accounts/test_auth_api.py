"""Registration, sign-in and session endpoints (ADR-0007)."""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.workspaces.models import Workspace, WorkspaceRole

pytestmark = pytest.mark.django_db

PASSWORD = "correct-horse-battery-9"
REGISTER, LOGIN, LOGOUT, ME = (
    "/api/v1/auth/register/",
    "/api/v1/auth/login/",
    "/api/v1/auth/logout/",
    "/api/v1/me/",
)


@pytest.fixture
def member(make_user):
    return make_user(password=PASSWORD)


def _login(client, email, password=PASSWORD, **extra):
    return client.post(LOGIN, {"email": email, "password": password}, format="json", **extra)


# --- Registration ----------------------------------------------------------


def test_registering_creates_the_user_and_exactly_one_personal_workspace(api_client):
    response = api_client.post(
        REGISTER, {"email": " New.Person@Example.com ", "password": PASSWORD}, format="json"
    )

    assert response.status_code == 201
    user = User.objects.get()
    assert user.email == "new.person@example.com"
    workspace = Workspace.objects.get(personal_owner=user)
    assert list(workspace.memberships.values_list("user_id", "role")) == [
        (user.pk, WorkspaceRole.OWNER)
    ]
    assert response.json() == {
        "id": str(user.public_id),
        "email": "new.person@example.com",
        "personal_workspace_id": str(workspace.public_id),
    }
    assert api_client.get(ME).status_code == 200  # signed in straight away
    assert AuditEvent.objects.filter(action="auth.registered", actor=user).exists()


def test_registering_an_existing_email_in_any_case_is_a_conflict(api_client, member):
    response = api_client.post(
        REGISTER, {"email": member.email.upper(), "password": PASSWORD}, format="json"
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"
    assert User.objects.count() == 1


def test_weak_passwords_are_rejected_with_field_details(api_client):
    response = api_client.post(
        REGISTER, {"email": "a@example.com", "password": "password123"}, format="json"
    )

    assert response.status_code == 400
    assert "password" in response.json()["error"]["details"]
    assert not User.objects.exists()


@pytest.mark.parametrize("url", [REGISTER, LOGIN])
def test_anonymous_writes_require_a_csrf_token(url):
    client = APIClient(enforce_csrf_checks=True)

    response = client.post(url, {"email": "a@example.com", "password": PASSWORD}, format="json")

    assert response.status_code == 403


def test_the_csrf_endpoint_sets_the_cookie(api_client):
    response = api_client.get("/api/v1/auth/csrf/")

    assert response.status_code == 204
    assert "csrftoken" in response.cookies


# --- Sign-in ----------------------------------------------------------------


def test_signing_in_by_email_in_any_case_starts_a_session(api_client, member):
    response = _login(api_client, member.email.upper())

    assert response.status_code == 200
    assert response.json()["email"] == member.email
    assert api_client.get(ME).status_code == 200
    assert AuditEvent.objects.filter(action="auth.login", actor=member).exists()


def test_first_sign_in_provisions_a_missing_personal_workspace(api_client, member):
    # make_user() bypasses registration, like createsuperuser does.
    assert not Workspace.objects.filter(personal_owner=member).exists()

    response = _login(api_client, member.email)

    workspace = Workspace.objects.get(personal_owner=member)
    assert response.json()["personal_workspace_id"] == str(workspace.public_id)


@pytest.mark.parametrize("case", ["wrong password", "unknown email", "inactive account"])
def test_failed_sign_in_reveals_nothing_and_is_audited(api_client, member, case):
    email, password = member.email, PASSWORD
    if case == "wrong password":
        password = "not-the-password-1"
    elif case == "unknown email":
        email = "nobody@example.com"
    else:
        User.objects.filter(pk=member.pk).update(is_active=False)

    response = _login(api_client, email, password)

    assert response.status_code == 401
    assert response["WWW-Authenticate"] == "Session"
    assert response.json()["error"]["code"] == "authentication_failed"
    assert response.json()["error"]["message"] == "Email or password is incorrect."
    event = AuditEvent.objects.get(action="auth.login_failed")
    assert event.metadata == {"email": email}  # never the password
    assert event.actor is None


def test_the_sixth_attempt_from_one_ip_within_a_minute_is_throttled(api_client, member):
    for _ in range(5):
        assert _login(api_client, member.email, "wrong-password-1").status_code == 401

    assert _login(api_client, member.email).status_code == 429


def test_the_sixth_attempt_on_one_email_from_different_ips_is_throttled(api_client, member):
    for n in range(5):
        _login(api_client, member.email, "wrong-password-1", REMOTE_ADDR=f"10.0.0.{n}")

    response = _login(api_client, member.email, REMOTE_ADDR="10.0.0.99")

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "throttled"


def test_a_sign_in_without_an_email_is_a_validation_error(api_client):
    response = api_client.post(LOGIN, {"password": PASSWORD}, format="json")

    assert response.status_code == 400
    assert "email" in response.json()["error"]["details"]


def test_the_django_admin_still_signs_in_by_username(client, member):
    assert client.login(username=member.username, password=PASSWORD)


# --- Session ------------------------------------------------------------------


def test_signing_out_ends_the_session(api_client, member):
    _login(api_client, member.email)

    assert api_client.post(LOGOUT).status_code == 204
    assert api_client.get(ME).status_code == 401


def test_me_requires_a_session(api_client):
    response = api_client.get(ME)

    assert response.status_code == 401
    assert response["WWW-Authenticate"] == "Session"
