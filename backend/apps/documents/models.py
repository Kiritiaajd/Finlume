"""SourceDocument: where a statement's figures came from."""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import PublicModel
from apps.workspaces.models import Workspace


class SourceDocumentKind(models.TextChoices):
    # csv_upload and its file columns (sha256, storage_key, ...) arrive with
    # CSV import in MVP step 4; pdf in Phase 2.
    MANUAL_ENTRY = "manual_entry", "Manual entry"


class SourceDocument(PublicModel):
    """Every statement has exactly one source (docs/data/DATA_MODEL.md §4.5)."""

    # No separate index: the (workspace, id) key below leads with workspace.
    workspace = models.ForeignKey(
        Workspace, on_delete=models.CASCADE, related_name="source_documents", db_index=False
    )
    kind = models.CharField(max_length=16, choices=SourceDocumentKind.choices)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(kind__in=SourceDocumentKind.values),
                name="documents_sourcedocument_kind_valid",
            ),
            # Target of the composite foreign key that keeps a statement and its
            # source in the same workspace (financial_records migration 0002).
            models.UniqueConstraint(
                fields=["workspace", "id"], name="documents_sourcedocument_workspace_key"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.kind} {self.public_id}"
