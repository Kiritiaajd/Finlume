"""Create and rename organizations."""

from __future__ import annotations

from django.db import transaction

from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.organizations.models import Organization, OrganizationMembership, OrganizationRole


@transaction.atomic
def create_organization(*, actor: User, name: str) -> Organization:
    """Any signed-in user may create an organization; they become its admin (ADR-0008, Q1)."""
    organization = Organization.objects.create(name=name, created_by=actor)
    OrganizationMembership.objects.create(
        organization=organization, user=actor, role=OrganizationRole.ADMIN
    )
    AuditEvent.record("organization.created", actor=actor, target=organization)
    return organization


def rename_organization(*, actor: User, organization: Organization, name: str) -> Organization:
    organization.name = name
    organization.save(update_fields=["name", "updated_at"])
    AuditEvent.record("organization.renamed", actor=actor, target=organization)
    return organization
