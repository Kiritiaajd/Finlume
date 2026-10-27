"""Abstract base model with the standard public_id and timestamp columns."""

from __future__ import annotations

import uuid

from django.db import models


class PublicModel(models.Model):
    """Standard columns (docs/data/DATABASE_CONVENTIONS.md).

    ``public_id`` is the only identifier used in URLs and payloads; the
    sequential primary key stays internal.
    """

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
