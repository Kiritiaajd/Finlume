from __future__ import annotations

import pytest

from apps.audit.models import AuditEvent
from apps.core.request_context import reset_request_id, set_request_id

pytestmark = pytest.mark.django_db


def test_events_carry_a_pseudonymous_actor_label_target_and_request_id(make_workspace):
    workspace = make_workspace()
    owner = workspace.memberships.get().user
    token = set_request_id("req-123")
    try:
        event = AuditEvent.record(
            "workspace.renamed", actor=owner, workspace=workspace, target=workspace, version=2
        )
    finally:
        reset_request_id(token)

    assert event.actor_label == f"user:{owner.public_id}"
    assert (event.target_type, event.target_public_id) == ("workspace", workspace.public_id)
    assert event.request_id == "req-123"
    assert event.metadata == {"version": 2}


def test_events_survive_their_actor_and_stay_attributable(make_user):
    user = make_user()
    event = AuditEvent.record("auth.login", actor=user)
    label = event.actor_label

    user.delete()
    event.refresh_from_db()

    assert event.actor is None
    assert event.actor_label == label


def test_anonymous_events_have_no_actor():
    event = AuditEvent.record("auth.login_failed", email="a@example.com")

    assert (event.actor, event.actor_label) == (None, "anonymous")
