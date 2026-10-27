"""Tenancy rows and users cannot be added, edited or deleted from the admin (ADR-0008 §7)."""

from __future__ import annotations

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


@pytest.fixture
def tenancy_rows(make_workspace):
    workspace = make_workspace()
    organization = workspace.organization
    return {
        "organizations_organization": organization,
        "organizations_organizationmembership": organization.memberships.get(),
        "workspaces_workspace": workspace,
        "workspaces_workspacemembership": workspace.memberships.get(),
    }


@pytest.mark.parametrize(
    "model",
    [
        "organizations_organization",
        "organizations_organizationmembership",
        "workspaces_workspace",
        "workspaces_workspacemembership",
    ],
)
def test_tenancy_admin_is_view_only(admin_client, tenancy_rows, model):
    obj = tenancy_rows[model]

    assert admin_client.get(reverse(f"admin:{model}_changelist")).status_code == 200
    assert admin_client.get(reverse(f"admin:{model}_add")).status_code == 403
    assert admin_client.get(reverse(f"admin:{model}_delete", args=[obj.pk])).status_code == 403
    change_page = admin_client.get(reverse(f"admin:{model}_change", args=[obj.pk]))
    assert change_page.status_code == 200
    assert b'name="_save"' not in change_page.content


def test_users_cannot_be_deleted_from_the_admin(admin_client, admin_user):
    url = reverse("admin:accounts_user_delete", args=[admin_user.pk])

    assert admin_client.get(url).status_code == 403
