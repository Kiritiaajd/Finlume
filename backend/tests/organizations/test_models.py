from __future__ import annotations

import pytest
from django.db import IntegrityError, transaction

from apps.organizations.models import OrganizationMembership, OrganizationRole

pytestmark = pytest.mark.django_db


def test_a_user_is_a_member_of_an_organization_at_most_once(make_organization):
    organization = make_organization()
    admin = organization.memberships.get().user

    with pytest.raises(IntegrityError), transaction.atomic():
        OrganizationMembership.objects.create(
            organization=organization, user=admin, role=OrganizationRole.MEMBER
        )


def test_organization_roles_are_checked_by_the_database(make_organization, make_user):
    with pytest.raises(IntegrityError), transaction.atomic():
        OrganizationMembership.objects.create(
            organization=make_organization(), user=make_user(), role="owner"
        )
