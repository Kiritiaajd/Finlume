#!/usr/bin/env python
"""Django's command-line utility. Defaults to development settings."""

import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Is the virtual environment active and are "
            "the backend requirements installed? See docs/development/LOCAL_SETUP.md."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
