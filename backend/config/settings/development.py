"""Local development settings. Never use these for a reachable deployment."""

from __future__ import annotations

import secrets

from config.env import env_list, env_str

from .base import *  # noqa: F403
from .base import REST_FRAMEWORK, build_databases

DEBUG = True

# Without DJANGO_SECRET_KEY a random per-process key is used: sessions simply
# reset on restart, and no key is ever committed to the repository.
SECRET_KEY = env_str("DJANGO_SECRET_KEY", default=secrets.token_urlsafe(50))

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# PostgreSQL by default, configured through POSTGRES_* (see .env.example).
# Startup fails with a clear message when they are missing; SQLite is used
# only when FINLUME_DB_ENGINE=sqlite is set deliberately.
DATABASES = build_databases(default_engine="postgresql")

#: Makes the finlume.W001 system check warn whenever development runs on SQLite.
FINLUME_WARN_IF_SQLITE = True

REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
}
