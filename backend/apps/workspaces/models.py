"""Workspace and WorkspaceMembership."""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import PublicModel
from apps.organizations.models import Organization


class WorkspaceRole(models.TextChoices):
    VIEWER = "viewer", "Viewer"
    EDITOR = "editor", "Editor"
    OWNER = "owner", "Owner"


class Workspace(PublicModel):
    """The tenancy boundary: a user's personal workspace, or an organization workspace.

    Exactly one of ``organization`` and ``personal_owner`` is set, so the kind
    is derived and can never disagree with a stored flag.
    """

    name = models.CharField(max_length=200)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="workspaces",
    )
    personal_owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="personal_workspace",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(organization__isnull=True, personal_owner__isnull=False)
                | Q(organization__isnull=False, personal_owner__isnull=True),
                name="workspaces_workspace_one_owner_kind",
            ),
        ]

    @property
    def is_personal(self) -> bool:
        return self.personal_owner_id is not None

    def __str__(self) -> str:
        return self.name


class WorkspaceMembership(PublicModel):
    """The only source of workspace access."""

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="memberships")
    # No separate index: the unique (user, workspace) index below leads with user
    # and is the index behind every access check.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="workspace_memberships",
        db_index=False,
    )
    role = models.CharField(max_length=16, choices=WorkspaceRole.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "workspace"], name="workspaces_workspacemembership_unique"
            ),
            models.CheckConstraint(
                condition=Q(role__in=WorkspaceRole.values),
                name="workspaces_workspacemembership_role_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} in {self.workspace_id} ({self.role})"
