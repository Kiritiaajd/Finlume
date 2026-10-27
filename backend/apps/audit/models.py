"""AuditEvent and its record() helper."""

from __future__ import annotations

import uuid
from typing import Any

from django.conf import settings
from django.db import models

from apps.accounts.models import User
from apps.core.request_context import get_request_id
from apps.workspaces.models import Workspace


class AuditEvent(models.Model):
    """Who did what, when. Append-only.

    Never holds financial values, document contents or credentials
    (docs/data/DATA_MODEL.md, AuditEvent). ``actor_label`` is a stable
    pseudonym, so an event stays attributable after the account is deleted.
    """

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    occurred_at = models.DateTimeField(auto_now_add=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    actor_label = models.CharField(max_length=64)
    workspace = models.ForeignKey(Workspace, on_delete=models.SET_NULL, null=True, related_name="+")
    action = models.CharField(max_length=64)
    target_type = models.CharField(max_length=64, blank=True)
    target_public_id = models.UUIDField(null=True)
    request_id = models.CharField(max_length=64)
    metadata = models.JSONField(default=dict)

    def __str__(self) -> str:
        return f"{self.action} by {self.actor_label}"

    @classmethod
    def record(
        cls,
        action: str,
        *,
        actor: User | None = None,
        workspace: Workspace | None = None,
        target: models.Model | None = None,
        **metadata: Any,
    ) -> AuditEvent:
        """Write one event. ``metadata`` must hold non-financial context only."""
        return cls.objects.create(
            action=action,
            actor=actor,
            actor_label=f"user:{actor.public_id}" if actor else "anonymous",
            workspace=workspace,
            target_type=(target._meta.model_name or "") if target is not None else "",
            target_public_id=getattr(target, "public_id", None),
            request_id=get_request_id(),
            metadata=metadata,
        )
