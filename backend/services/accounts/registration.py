"""Register a user together with their personal workspace and owner membership."""

from __future__ import annotations

import uuid

from django.db import IntegrityError, transaction

from apps.accounts.backends import normalize_email
from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.workspaces.models import Workspace, WorkspaceMembership, WorkspaceRole
from services.errors import ConflictError

PERSONAL_WORKSPACE_NAME = "Personal"


@transaction.atomic
def register_user(*, email: str, password: str) -> User:
    """Create an account with its personal workspace, all or nothing (invariant I1).

    Duplicate emails are detected by the database's case-insensitive unique
    index, not by a prior lookup, so there is no race between check and insert.
    """
    try:
        with transaction.atomic():
            # ``username`` serves only the Django admin; API users sign in by email.
            user = User.objects.create_user(
                username=uuid.uuid4().hex, email=normalize_email(email), password=password
            )
    except IntegrityError:
        raise ConflictError("An account with this email address already exists.") from None
    _create_personal_workspace(user)
    AuditEvent.record("auth.registered", actor=user, target=user)
    return user


def ensure_personal_workspace(user: User) -> None:
    """Give ``user`` a personal workspace if they lack one (invariant I1).

    Covers accounts created outside registration, such as with
    ``createsuperuser``. One indexed query when the workspace already exists.
    """
    if Workspace.objects.filter(personal_owner=user).exists():
        return
    try:
        with transaction.atomic():
            _create_personal_workspace(user)
    except IntegrityError:
        pass  # a concurrent sign-in created it first


def _create_personal_workspace(user: User) -> Workspace:
    workspace = Workspace.objects.create(
        name=PERSONAL_WORKSPACE_NAME, personal_owner=user, created_by=user
    )
    WorkspaceMembership.objects.create(workspace=workspace, user=user, role=WorkspaceRole.OWNER)
    return workspace
