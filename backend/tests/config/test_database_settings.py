"""Which database each settings module selects, and how misconfiguration fails.

Settings are imported in a subprocess with every database variable given
explicitly (empty means unset), so a developer's local .env cannot leak in.
Nothing here connects to a database.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]

NO_DATABASE_ENV = {
    "FINLUME_DB_ENGINE": "",
    "FINLUME_TEST_DB_ENGINE": "",
    "POSTGRES_DB": "",
    "POSTGRES_USER": "",
    "POSTGRES_PASSWORD": "",
    "POSTGRES_PORT": "",
    "DJANGO_SETTINGS_MODULE": "",
}
POSTGRES_ENV = {
    "POSTGRES_DB": "finlume",
    "POSTGRES_USER": "finlume",
    "POSTGRES_PASSWORD": "placeholder",
    # Reserved name (RFC 2606) that never resolves: even an accidental
    # connection attempt could not reach a real server.
    "POSTGRES_HOST": "postgres.invalid",
    "POSTGRES_PORT": "55432",
}

PROBE = (
    "import importlib, json, sys;"
    "d = importlib.import_module(sys.argv[1]).DATABASES['default'];"
    "print(json.dumps({'engine': d['ENGINE'].rsplit('.', 1)[-1], 'name': str(d['NAME']),"
    " 'port': d.get('PORT')}))"
)


def _run(args: list[str], **env: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - fixed interpreter and arguments
        [sys.executable, *args],
        cwd=BACKEND_DIR,
        env={**os.environ, **NO_DATABASE_ENV, **env},
        capture_output=True,
        text=True,
        check=False,
    )


def _database(settings_module: str, **env: str) -> dict[str, Any]:
    result = _run(["-c", PROBE, settings_module], **env)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _error(settings_module: str, **env: str) -> str:
    result = _run(["-c", PROBE, settings_module], **env)
    assert result.returncode != 0
    return result.stderr


# --- development -------------------------------------------------------------


def test_development_defaults_to_postgresql():
    database = _database("config.settings.development", **POSTGRES_ENV)

    assert database == {"engine": "postgresql", "name": "finlume", "port": 55432}


def test_development_without_postgres_settings_fails_with_every_missing_variable():
    stderr = _error("config.settings.development")

    assert "PostgreSQL is selected (the default)" in stderr
    assert "POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD are not set" in stderr
    assert "Copy .env.example to .env" in stderr
    assert "FINLUME_DB_ENGINE=sqlite" in stderr


def test_development_never_falls_back_to_sqlite_on_partial_configuration():
    stderr = _error("config.settings.development", POSTGRES_DB="finlume", POSTGRES_USER="finlume")

    assert "POSTGRES_PASSWORD is not set" in stderr


def test_development_uses_sqlite_only_when_explicitly_selected():
    database = _database("config.settings.development", FINLUME_DB_ENGINE="sqlite")

    assert database["engine"] == "sqlite3"
    assert database["name"].endswith("local.sqlite3")


def test_unknown_engine_is_rejected():
    stderr = _error("config.settings.development", FINLUME_DB_ENGINE="mysql")

    assert "FINLUME_DB_ENGINE must be one of" in stderr


@pytest.mark.parametrize(
    ("engine_env", "expect_warning"),
    [({"FINLUME_DB_ENGINE": "sqlite"}, True), (POSTGRES_ENV, False)],
)
def test_development_warns_about_the_sqlite_opt_in(engine_env, expect_warning):
    # `check` does not connect to the database.
    result = _run(["manage.py", "check", "--settings=config.settings.development"], **engine_env)

    assert result.returncode == 0, result.stderr
    assert ("finlume.W001" in result.stderr) is expect_warning


# --- tests ---------------------------------------------------------------------


def test_test_settings_ignore_the_development_engine():
    database = _database("config.settings.test", FINLUME_DB_ENGINE="postgresql", **POSTGRES_ENV)

    assert database["engine"] == "sqlite3"
    assert database["name"].endswith("test.sqlite3")


def test_test_settings_use_postgresql_when_asked():
    database = _database(
        "config.settings.test", FINLUME_TEST_DB_ENGINE="postgresql", **POSTGRES_ENV
    )

    assert database["engine"] == "postgresql"


def test_test_settings_name_their_own_variable_in_errors():
    stderr = _error("config.settings.test", FINLUME_TEST_DB_ENGINE="postgresql")

    assert "PostgreSQL is selected (FINLUME_TEST_DB_ENGINE)" in stderr
    assert "FINLUME_TEST_DB_ENGINE=sqlite" in stderr


# --- production (unchanged behaviour) ------------------------------------------


def test_production_still_defaults_to_postgresql():
    database = _database(
        "config.settings.production",
        DJANGO_SECRET_KEY="x" * 64,
        DJANGO_ALLOWED_HOSTS="finlume.example.org",
        **POSTGRES_ENV,
    )

    assert database["engine"] == "postgresql"
