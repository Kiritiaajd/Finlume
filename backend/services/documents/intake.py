"""Uploaded files: content checks, SHA-256 and private storage (ADR-0005, MVP step 4).

The size limit is enforced by the upload endpoint before any of this runs, so
a file that is too large never reaches storage. A file is stored under a
random key in the ``private_documents`` storage, which has no URL; the
upload's own name is kept only for display.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass

from django.core.files.base import ContentFile
from django.core.files.storage import storages

from apps.workspaces.models import Workspace
from services.errors import InvalidInput

CSV_CONTENT_TYPE = "text/csv"


@dataclass(frozen=True)
class StoredFile:
    storage_key: str
    sha256: str
    size_bytes: int


def decode_csv(data: bytes) -> str:
    """The file's text, if it really is UTF-8 text; the client's content type is not trusted.

    A UTF-8 byte-order mark, as spreadsheet programs write, is accepted.
    """
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise InvalidInput({"file": ["The file must be UTF-8 text (CSV)."]}) from None
    if "\x00" in text:
        raise InvalidInput({"file": ["The file must be UTF-8 text (CSV), not a binary file."]})
    return text


def fingerprint(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def store_file(*, workspace: Workspace, data: bytes) -> StoredFile:
    """Write ``data`` to private storage under a random key, never the upload's name."""
    key = f"documents/{workspace.public_id}/{uuid.uuid4().hex}"
    stored = storages["private_documents"].save(key, ContentFile(data))
    return StoredFile(storage_key=stored, sha256=fingerprint(data), size_bytes=len(data))


def delete_file(storage_key: str) -> None:
    """Remove a stored file whose database row was not created."""
    storages["private_documents"].delete(storage_key)
