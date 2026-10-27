"""Organization and OrganizationMembership."""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import PublicModel


class OrganizationRole(models.TextChoices):
    ADMIN = "admin", "Admin"
    MEMBER = "member", "Member"


class Organization(PublicModel):
    """The customer boundary. Membership in it grants no workspace access (ADR-0008)."""

    name = models.CharField(max_length=200)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )

    def __str__(self) -> str:
        return self.name


class OrganizationMembership(PublicModel):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    # No separate index: the unique (user, organization) index below leads with user.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organization_memberships",
        db_index=False,
    )
    role = models.CharField(max_length=16, choices=OrganizationRole.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "organization"],
                name="organizations_organizationmembership_unique",
            ),
            models.CheckConstraint(
                condition=Q(role__in=OrganizationRole.values),
                name="organizations_organizationmembership_role_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} in {self.organization_id} ({self.role})"
