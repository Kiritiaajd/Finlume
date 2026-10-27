from __future__ import annotations

import pytest

from apps.accounts.models import User
from apps.workspaces.models import Workspace
from services.accounts import ensure_personal_workspace, register_user, registration
from services.errors import ConflictError

pytestmark = pytest.mark.django_db

PASSWORD = "correct-horse-battery-9"


def test_registration_is_all_or_nothing(monkeypatch):
    def fail(user):
        raise RuntimeError("workspace insert failed")

    monkeypatch.setattr(registration, "_create_personal_workspace", fail)

    with pytest.raises(RuntimeError):
        register_user(email="a@example.com", password=PASSWORD)

    assert not User.objects.exists()


def test_duplicate_emails_raise_a_conflict_without_a_partial_account():
    register_user(email="a@example.com", password=PASSWORD)

    with pytest.raises(ConflictError):
        register_user(email="A@Example.com", password=PASSWORD)

    assert User.objects.count() == 1
    assert Workspace.objects.count() == 1


def test_ensure_personal_workspace_is_idempotent_and_cheap_once_provisioned(
    make_user, django_assert_num_queries
):
    user = make_user()

    ensure_personal_workspace(user)
    with django_assert_num_queries(1):
        ensure_personal_workspace(user)

    assert Workspace.objects.filter(personal_owner=user).count() == 1
