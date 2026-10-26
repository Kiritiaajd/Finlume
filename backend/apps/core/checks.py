"""``manage.py check`` rules for the local database configuration."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core import checks
from django.core.checks import CheckMessage, register


@register("database_config")
def check_development_database(app_configs: Any, **kwargs: Any) -> list[CheckMessage]:
    """Warn when development settings run on the explicit SQLite opt-in."""
    if not getattr(settings, "FINLUME_WARN_IF_SQLITE", False):
        return []
    if settings.DATABASES["default"]["ENGINE"] != "django.db.backends.sqlite3":
        return []
    return [
        checks.Warning(
            "Development is running on SQLite because FINLUME_DB_ENGINE=sqlite is set.",
            hint=(
                "SQLite is for throwaway trials only: it does not preserve decimal precision "
                "like PostgreSQL. Remove FINLUME_DB_ENGINE=sqlite and configure POSTGRES_* "
                "in .env to use PostgreSQL."
            ),
            id="finlume.W001",
        )
    ]
