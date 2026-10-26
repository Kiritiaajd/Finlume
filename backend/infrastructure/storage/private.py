from __future__ import annotations

from typing import Any

from django.core.files.storage import FileSystemStorage


class PublicURLNotAllowedError(RuntimeError):
    """Raised when code asks private storage for a public URL."""


class PrivateFileSystemStorage(FileSystemStorage):
    """Filesystem storage for sensitive uploads that can never yield a public URL.

    Files are written owner-only. Access goes through an authenticated API
    view that checks object ownership and streams the file; there is no URL a
    browser could fetch directly. An object-storage implementation (e.g. S3
    with private buckets and short-lived signed URLs) can replace this class
    via the ``STORAGES`` setting without changing callers.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("file_permissions_mode", 0o600)
        kwargs.setdefault("directory_permissions_mode", 0o700)
        kwargs["base_url"] = None
        super().__init__(**kwargs)

    def url(self, name: str | None) -> str:
        raise PublicURLNotAllowedError(
            "Private documents have no public URL; serve them through an "
            "authenticated, ownership-checked API endpoint."
        )
