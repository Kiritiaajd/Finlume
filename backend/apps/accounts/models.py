from __future__ import annotations

import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower


class User(AbstractUser):
    """Finlume user account.

    Defined before the first migration because Django cannot cleanly swap the
    user model later. ``public_id`` is the identifier exposed through the API;
    the sequential primary key stays internal so record counts and IDs cannot
    be enumerated.
    """

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    email = models.EmailField("email address")

    class Meta:
        constraints = [
            # Case-insensitive: "A@example.com" and "a@example.com" are one person.
            models.UniqueConstraint(Lower("email"), name="accounts_user_email_ci_unique"),
        ]

    def __str__(self) -> str:
        return self.username
