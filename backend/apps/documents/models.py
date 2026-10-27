"""SourceDocument: where a statement's figures came from."""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import PublicModel
from apps.workspaces.models import Workspace


class SourceDocumentKind(models.TextChoices):
    MANUAL_ENTRY = "manual_entry", "Manual entry"
    CSV_UPLOAD = "csv_upload", "CSV upload"
    # pdf arrives in Phase 2, provider in Phase 5.


class SourceDocument(PublicModel):
    """Every statement has exactly one source (docs/data/DATA_MODEL.md §4.5).

    An uploaded file is kept in the ``private_documents`` storage under a random
    ``storage_key``, never a name derived from the upload, and it has no URL.
    ``original_filename`` is for display only.
    """

    # No separate index: the (workspace, id) key below leads with workspace.
    workspace = models.ForeignKey(
        Workspace, on_delete=models.CASCADE, related_name="source_documents", db_index=False
    )
    kind = models.CharField(max_length=16, choices=SourceDocumentKind.choices)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    # File kinds only; blank for manual entry.
    original_filename = models.CharField(max_length=255, blank=True)
    content_type = models.CharField(max_length=100, blank=True)
    size_bytes = models.PositiveBigIntegerField(null=True, blank=True)
    sha256 = models.CharField(max_length=64, blank=True)
    storage_key = models.CharField(max_length=255, blank=True)
    # The client's Idempotency-Key for the upload that created this document.
    idempotency_key = models.UUIDField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(kind__in=SourceDocumentKind.values),
                name="documents_sourcedocument_kind_valid",
            ),
            # Manual entry has no file; a file has its fingerprint, size and key.
            models.CheckConstraint(
                condition=Q(
                    kind=SourceDocumentKind.MANUAL_ENTRY,
                    original_filename="",
                    content_type="",
                    size_bytes__isnull=True,
                    sha256="",
                    storage_key="",
                )
                | (
                    ~Q(kind=SourceDocumentKind.MANUAL_ENTRY)
                    & Q(size_bytes__isnull=False, sha256__regex=r"^[0-9a-f]{64}$")
                    & ~Q(storage_key="")
                ),
                name="documents_sourcedocument_file_fields",
            ),
            models.UniqueConstraint(
                fields=["workspace", "created_by", "idempotency_key"],
                condition=Q(idempotency_key__isnull=False),
                name="documents_sourcedocument_idempotency_unique",
            ),
            # Target of the composite foreign key that keeps a statement and its
            # source in the same workspace (financial_records migration 0002).
            models.UniqueConstraint(
                fields=["workspace", "id"], name="documents_sourcedocument_workspace_key"
            ),
        ]
        indexes = [
            # Finds an earlier upload of the same file (a warning, not a refusal).
            models.Index(fields=["workspace", "sha256"], name="doc_ws_sha256_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.kind} {self.public_id}"
