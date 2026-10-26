from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "apps.core"
    label = "core"
    verbose_name = "Core"

    def ready(self) -> None:
        # Registers deployment safety checks with `manage.py check`.
        from infrastructure.storage import checks  # noqa: F401

        from . import checks as database_checks  # noqa: F401
