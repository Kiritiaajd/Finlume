from __future__ import annotations

import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.test import override_settings

from infrastructure.storage.checks import check_private_storage_location
from infrastructure.storage.private import PrivateFileSystemStorage, PublicURLNotAllowedError


def test_private_storage_round_trips_files(tmp_path):
    storage = PrivateFileSystemStorage(location=tmp_path)

    name = storage.save("statements/sample.csv", ContentFile(b"line_item,amount\n"))

    with storage.open(name) as handle:
        assert handle.read() == b"line_item,amount\n"


def test_private_storage_never_produces_a_url(tmp_path):
    storage = PrivateFileSystemStorage(location=tmp_path)

    with pytest.raises(PublicURLNotAllowedError):
        storage.url("statements/sample.csv")


@pytest.mark.parametrize("alias", ["default", "private_documents"])
def test_configured_storages_are_private(alias):
    assert isinstance(storages[alias], PrivateFileSystemStorage)


def test_check_passes_for_the_configured_location():
    assert check_private_storage_location(None) == []


def test_check_rejects_private_root_inside_static_root(tmp_path):
    with override_settings(STATIC_ROOT=tmp_path, PRIVATE_STORAGE_ROOT=tmp_path / "private"):
        errors = check_private_storage_location(None)

    assert [error.id for error in errors] == ["finlume.E001"]
