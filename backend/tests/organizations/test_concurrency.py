"""Organization invariants under concurrent requests.

PostgreSQL only: SQLite has no row locks (``SELECT ... FOR UPDATE``).
"""

from __future__ import annotations

import threading

import pytest
from django.db import connection

from apps.organizations.models import OrganizationMembership, OrganizationRole
from apps.workspaces.models import WorkspaceMembership, WorkspaceRole
from services import organizations, workspaces
from services.errors import ConflictError

pytestmark = [pytest.mark.postgres, pytest.mark.django_db(transaction=True)]


def run_together(*calls):
    """Start every call at the same moment, each on its own connection; return outcomes."""
    start = threading.Barrier(len(calls))
    outcomes: list[str] = []

    def run(call):
        try:
            start.wait()
            call()
            outcomes.append("done")
        except ConflictError:
            outcomes.append("conflict")
        finally:
            connection.close()

    threads = [threading.Thread(target=run, args=(call,)) for call in calls]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    return sorted(outcomes)


def test_concurrent_demotions_keep_one_admin(make_organization, make_user):
    organization = make_organization()
    first = organization.memberships.get().user
    second = make_user()
    OrganizationMembership.objects.create(
        organization=organization, user=second, role=OrganizationRole.ADMIN
    )

    def demote(actor, target):
        return lambda: organizations.change_member_role(
            actor=actor,
            organization=organization,
            user_id=target.public_id,
            role=OrganizationRole.MEMBER,
        )

    assert run_together(demote(first, second), demote(second, first)) == ["conflict", "done"]
    assert organization.memberships.filter(role=OrganizationRole.ADMIN).count() == 1


def test_a_workspace_membership_added_during_removal_from_the_organization_is_not_left_behind(
    make_workspace, make_user
):
    workspace = make_workspace()
    organization, owner = workspace.organization, workspace.memberships.get().user
    target = make_user()
    OrganizationMembership.objects.create(
        organization=organization, user=target, role=OrganizationRole.MEMBER
    )

    outcomes = run_together(
        lambda: organizations.remove_member(
            actor=owner,
            actor_role=OrganizationRole.ADMIN,
            organization=organization,
            user_id=target.public_id,
        ),
        lambda: workspaces.add_member(
            actor=owner, workspace=workspace, user_id=target.public_id, role=WorkspaceRole.VIEWER
        ),
    )

    # Whichever runs first, the removal wins in the end and I2 holds.
    assert outcomes in (["done", "done"], ["conflict", "done"])
    assert not OrganizationMembership.objects.filter(
        organization=organization, user=target
    ).exists()
    assert not WorkspaceMembership.objects.filter(user=target).exists()
