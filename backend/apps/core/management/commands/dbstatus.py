"""Read-only database status for developers and the dev launchers.

    python manage.py dbstatus

Shows which database the settings point to (never the password), checks that
it is reachable and supported, and lists pending migrations. It never writes:
no migrations, no table creation, no data changes.

Exit codes: 0 reachable and up to date, 2 unreachable or unsupported,
3 reachable with pending migrations. A configuration error stops Django
before this command runs (exit code 1).
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import DEFAULT_DB_ALIAS, DatabaseError, connections
from django.db.migrations.executor import MigrationExecutor
from django.db.utils import NotSupportedError

UNREACHABLE = 2
PENDING_MIGRATIONS = 3


def describe_database(settings_dict: dict[str, Any]) -> str:
    """Human-readable target without credentials beyond the user name."""
    engine = str(settings_dict["ENGINE"]).rsplit(".", 1)[-1]
    if engine == "sqlite3":
        return f"SQLite at {settings_dict['NAME']}"
    host = settings_dict.get("HOST") or "localhost"
    port = settings_dict.get("PORT") or "default port"
    return (
        f"PostgreSQL database {settings_dict['NAME']!r} as user {settings_dict['USER']!r} "
        f"on {host}:{port}"
    )


class Command(BaseCommand):
    help = (
        "Show the configured database, check that it is reachable and list pending "
        "migrations. Read-only."
    )

    # This command diagnoses the database; it must not depend on it being healthy.
    requires_system_checks = ()
    requires_migrations_checks = False

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--database", default=DEFAULT_DB_ALIAS)

    def handle(self, *args: Any, **options: Any) -> None:
        connection = connections[options["database"]]
        self.stdout.write(f"Database: {describe_database(connection.settings_dict)}")

        try:
            connection.ensure_connection()
            connection.check_database_version_supported()
            version = ".".join(str(part) for part in connection.get_database_version())
        except (DatabaseError, NotSupportedError) as exc:
            reason = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
            raise CommandError(
                f"Cannot use the database: {reason}", returncode=UNREACHABLE
            ) from exc
        self.stdout.write(f"Connection: OK (server version {version})")

        # Reads django_migrations if it exists; never creates it.
        executor = MigrationExecutor(connection)
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())

        if plan:
            names = ", ".join(f"{migration.app_label}.{migration.name}" for migration, _ in plan)
            raise CommandError(
                f"{len(plan)} pending migration(s): {names}. "
                "Review them, then run 'python manage.py migrate' yourself.",
                returncode=PENDING_MIGRATIONS,
            )
        self.stdout.write("Migrations: up to date")
