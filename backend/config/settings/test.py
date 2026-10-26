"""Settings for the pytest suite.

The test database is chosen by its own variable, ``FINLUME_TEST_DB_ENGINE``
(default ``sqlite``, in memory), independent of the development database in
``FINLUME_DB_ENGINE``. Local runs therefore never create or drop databases on
your PostgreSQL server unless you ask for it. CI sets
``FINLUME_TEST_DB_ENGINE=postgresql`` and is the authoritative result.
"""

from __future__ import annotations

import secrets

from .base import *  # noqa: F403
from .base import BASE_DIR, REST_FRAMEWORK, STORAGES, build_databases

DEBUG = False
SECRET_KEY = secrets.token_urlsafe(50)
ALLOWED_HOSTS = ["testserver", "localhost"]

DATABASES = build_databases(default_engine="sqlite", engine_variable="FINLUME_TEST_DB_ENGINE")
if DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3":
    # Never point management commands run with test settings at the developer's
    # local database; pytest itself uses an in-memory SQLite database.
    DATABASES["default"]["NAME"] = BASE_DIR / "var" / "test.sqlite3"

# Fast hashing keeps the suite quick; never use outside tests.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

PRIVATE_STORAGE_ROOT = BASE_DIR / "var" / "test-private"
STORAGES = {
    **STORAGES,
    "default": {**STORAGES["default"], "OPTIONS": {"location": PRIVATE_STORAGE_ROOT}},
    "private_documents": {
        **STORAGES["private_documents"],
        "OPTIONS": {"location": PRIVATE_STORAGE_ROOT},
    },
}

# Throttling is exercised by dedicated tests, not by every request.
REST_FRAMEWORK = {**REST_FRAMEWORK, "DEFAULT_THROTTLE_CLASSES": []}
