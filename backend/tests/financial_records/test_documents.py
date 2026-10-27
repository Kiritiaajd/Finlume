"""SourceDocument constraints and admin for uploaded files (DATA_MODEL §4.5, FA-21)."""

from __future__ import annotations

import pytest
from django.db import IntegrityError, transaction
from django.urls import reverse

from apps.documents.models import SourceDocument, SourceDocumentKind

pytestmark = pytest.mark.django_db

SHA = "a" * 64


@pytest.fixture
def csv_fields():
    return {
        "kind": SourceDocumentKind.CSV_UPLOAD,
        "original_filename": "fy25.csv",
        "content_type": "text/csv",
        "size_bytes": 42,
        "sha256": SHA,
        "storage_key": "documents/x/abc",
    }


def test_an_uploaded_file_has_its_fingerprint_size_and_key(make_workspace, csv_fields):
    assert SourceDocument.objects.create(workspace=make_workspace(), **csv_fields).pk


@pytest.mark.parametrize(
    "change",
    [
        {"sha256": ""},
        {"sha256": "A" * 64},  # lowercase hex only
        {"sha256": "a" * 63},
        {"storage_key": ""},
        {"size_bytes": None},
    ],
)
def test_an_upload_without_a_valid_fingerprint_size_or_key_is_rejected(
    make_workspace, csv_fields, change
):
    with pytest.raises(IntegrityError, match="file_fields"), transaction.atomic():
        SourceDocument.objects.create(workspace=make_workspace(), **{**csv_fields, **change})


@pytest.mark.parametrize(
    "file_field",
    [{"sha256": SHA}, {"storage_key": "k"}, {"size_bytes": 1}, {"original_filename": "x"}],
)
def test_manual_entry_has_no_file(make_workspace, file_field):
    with pytest.raises(IntegrityError, match="file_fields"), transaction.atomic():
        SourceDocument.objects.create(
            workspace=make_workspace(), kind=SourceDocumentKind.MANUAL_ENTRY, **file_field
        )


def test_an_idempotency_key_is_used_once_per_user_and_workspace(
    make_workspace, make_user, csv_fields
):
    workspace, user = make_workspace(), make_user()
    key = "8d1f4a54-3b1c-4c5e-9f8a-2a7f0e9b6c11"
    SourceDocument.objects.create(
        workspace=workspace, created_by=user, idempotency_key=key, **csv_fields
    )
    SourceDocument.objects.create(  # another user may use the same key
        workspace=workspace, created_by=make_user(), idempotency_key=key, **csv_fields
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        SourceDocument.objects.create(
            workspace=workspace, created_by=user, idempotency_key=key, **csv_fields
        )


def test_the_admin_shows_an_uploaded_file_without_a_link(admin_client, make_workspace, csv_fields):
    document = SourceDocument.objects.create(workspace=make_workspace(), **csv_fields)

    page = admin_client.get(reverse("admin:documents_sourcedocument_change", args=[document.pk]))

    assert page.status_code == 200
    assert b"fy25.csv" in page.content
    assert b'name="_save"' not in page.content
