"""Two owners demoting each other at the same moment must not leave a workspace ownerless.

PostgreSQL only: SQLite has no row locks (``SELECT ... FOR UPDATE``).
"""

from __future__ import annotations

import threading

import pytest
from django.db import connection

from apps.workspaces.models import WorkspaceMembership, WorkspaceRole
from services.errors import ConflictError
from services.workspaces import change_member_role

pytestmark = [pytest.mark.postgres, pytest.mark.django_db(transaction=True)]


def test_concurrent_demotions_keep_one_owner(make_workspace, add_to_workspace):
    workspace = make_workspace()
    first = workspace.memberships.get().user
    second = add_to_workspace(workspace, WorkspaceRole.OWNER)
    start = threading.Barrier(2)
    outcomes: list[str] = []

    def demote(actor, target):
        try:
            start.wait()
            change_member_role(
                actor=actor,
                workspace=workspace,
                user_id=target.public_id,
                role=WorkspaceRole.VIEWER,
            )
            outcomes.append("demoted")
        except ConflictError:
            outcomes.append("conflict")
        finally:
            connection.close()  # each thread has its own connection

    threads = [
        threading.Thread(target=demote, args=(first, second)),
        threading.Thread(target=demote, args=(second, first)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert sorted(outcomes) == ["conflict", "demoted"]
    assert (
        WorkspaceMembership.objects.filter(workspace=workspace, role=WorkspaceRole.OWNER).count()
        == 1
    )
