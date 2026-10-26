from __future__ import annotations

from io import StringIO
from types import SimpleNamespace

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import OperationalError, connections
from django.db.migrations.executor import MigrationExecutor

from apps.core.management.commands.dbstatus import (
    PENDING_MIGRATIONS,
    UNREACHABLE,
    describe_database,
)


def _dbstatus() -> str:
    output = StringIO()
    call_command("dbstatus", stdout=output)
    return output.getvalue()


@pytest.mark.django_db
def test_reports_a_reachable_up_to_date_database():
    output = _dbstatus()

    assert "Connection: OK" in output
    assert "Migrations: up to date" in output


@pytest.mark.django_db
def test_reports_pending_migrations_without_applying_them(monkeypatch):
    fake = SimpleNamespace(app_label="accounts", name="0002_example")
    monkeypatch.setattr(MigrationExecutor, "migration_plan", lambda self, targets: [(fake, False)])

    with pytest.raises(
        CommandError, match=r"1 pending migration\(s\): accounts\.0002_example"
    ) as exc:
        _dbstatus()

    assert exc.value.returncode == PENDING_MIGRATIONS


@pytest.mark.django_db
def test_reports_an_unreachable_database(monkeypatch):
    def refuse() -> None:
        raise OperationalError('connection to server at "127.0.0.1", port 55432 failed\ndetail')

    monkeypatch.setattr(connections["default"], "ensure_connection", refuse)

    with pytest.raises(CommandError, match=r"port 55432 failed$") as exc:
        _dbstatus()

    assert exc.value.returncode == UNREACHABLE


def test_describes_postgresql_without_the_password():
    description = describe_database(
        {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": "finlume",
            "USER": "finlume",
            "PASSWORD": "never-shown",
            "HOST": "localhost",
            "PORT": 55432,
        }
    )

    assert description == "PostgreSQL database 'finlume' as user 'finlume' on localhost:55432"
    assert "never-shown" not in description


def test_describes_sqlite():
    assert describe_database({"ENGINE": "django.db.backends.sqlite3", "NAME": "x.sqlite3"}) == (
        "SQLite at x.sqlite3"
    )
