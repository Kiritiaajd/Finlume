from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from apps.accounts.models import User


def test_custom_user_model_is_active():
    assert get_user_model() is User


@pytest.mark.django_db
def test_users_get_a_distinct_public_id():
    first = User.objects.create_user("first", email="first@example.com")
    second = User.objects.create_user("second", email="second@example.com")

    assert first.public_id != second.public_id


@pytest.mark.django_db
def test_email_is_unique_regardless_of_case():
    User.objects.create_user("first", email="person@example.com")

    with pytest.raises(IntegrityError):
        User.objects.create_user("second", email="Person@Example.com")
