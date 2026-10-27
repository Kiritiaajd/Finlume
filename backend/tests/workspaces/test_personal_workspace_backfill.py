from __future__ import annotations

import importlib

import pytest
from django.apps import apps

from apps.workspaces.models import Workspace, WorkspaceMembership, WorkspaceRole

pytestmark = pytest.mark.django_db

backfill = importlib.import_module("apps.workspaces.migrations.0002_backfill_personal_workspaces")


def test_every_user_gets_exactly_one_personal_workspace_and_rerunning_is_harmless(
    make_user, monkeypatch
):
    monkeypatch.setattr(backfill, "BATCH_SIZE", 2)  # exercise several batches
    users = [make_user() for _ in range(5)]
    existing = Workspace.objects.create(
        name="Already there", personal_owner=users[0], created_by=users[0]
    )
    WorkspaceMembership.objects.create(workspace=existing, user=users[0], role=WorkspaceRole.OWNER)

    backfill.create_personal_workspaces(apps, None)
    backfill.create_personal_workspaces(apps, None)

    for user in users:
        workspace = Workspace.objects.get(personal_owner=user)
        assert list(workspace.memberships.values_list("user_id", "role")) == [
            (user.pk, WorkspaceRole.OWNER)
        ]
    assert Workspace.objects.get(personal_owner=users[0]).name == "Already there"
    assert Workspace.objects.count() == len(users)
