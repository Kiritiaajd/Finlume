"""Production settings must refuse to start with unsafe configuration."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command

BACKEND_DIR = Path(__file__).resolve().parents[2]

VALID_PRODUCTION_ENV = {
    "DJANGO_SECRET_KEY": "x" * 64,
    "DJANGO_ALLOWED_HOSTS": "finlume.example.org",
    "FINLUME_DB_ENGINE": "postgresql",
    "POSTGRES_DB": "finlume",
    "POSTGRES_USER": "finlume",
    "POSTGRES_PASSWORD": "placeholder",
}


def _import_production_settings(**overrides: str) -> subprocess.CompletedProcess[str]:
    # Explicit values (even empty ones) take precedence over any local .env.
    env = {**os.environ, **VALID_PRODUCTION_ENV, **overrides}
    return subprocess.run(
        [sys.executable, "-c", "import config.settings.production"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_valid_production_configuration_loads():
    result = _import_production_settings()

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"DJANGO_SECRET_KEY": ""}, "DJANGO_SECRET_KEY"),
        ({"DJANGO_SECRET_KEY": "too-short"}, "at least 50 characters"),
        ({"DJANGO_ALLOWED_HOSTS": ""}, "DJANGO_ALLOWED_HOSTS"),
        ({"FINLUME_DB_ENGINE": "sqlite"}, "must use PostgreSQL"),
        ({"POSTGRES_PASSWORD": ""}, "POSTGRES_PASSWORD"),
    ],
)
def test_unsafe_production_configuration_is_rejected(overrides, message):
    result = _import_production_settings(**overrides)

    assert result.returncode != 0
    assert message in result.stderr


def test_production_hardening_flags():
    probe = (
        "import json, config.settings.production as s; print(json.dumps({"
        "'debug': s.DEBUG, 'ssl_redirect': s.SECURE_SSL_REDIRECT,"
        "'session_secure': s.SESSION_COOKIE_SECURE, 'csrf_secure': s.CSRF_COOKIE_SECURE,"
        "'renderers': s.REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'],"
        "'permissions': s.REST_FRAMEWORK['DEFAULT_PERMISSION_CLASSES'],"
        "'proxy_header': getattr(s, 'SECURE_PROXY_SSL_HEADER', None)}))"
    )
    env = {**os.environ, **VALID_PRODUCTION_ENV, "FINLUME_TRUST_PROXY_SSL_HEADER": ""}
    result = subprocess.run(  # noqa: S603 - fixed interpreter and constant probe code
        [sys.executable, "-c", probe],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    flags = json.loads(result.stdout)
    assert flags == {
        "debug": False,
        "ssl_redirect": True,
        "session_secure": True,
        "csrf_secure": True,
        "renderers": ["rest_framework.renderers.JSONRenderer"],
        "permissions": ["rest_framework.permissions.IsAuthenticated"],
        "proxy_header": None,
    }


@pytest.mark.django_db
def test_models_and_migrations_are_in_sync():
    output = StringIO()

    call_command("makemigrations", "--check", "--dry-run", stdout=output)
