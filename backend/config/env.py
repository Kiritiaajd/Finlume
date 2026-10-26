"""Typed access to environment variables for Django settings.

Settings read configuration exclusively through these helpers so that a
missing or malformed value fails loudly at startup instead of silently
falling back to an unsafe default.
"""

from __future__ import annotations

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off"})
_MISSING = object()


def load_env_file(path: Path) -> None:
    """Load ``KEY=VALUE`` lines from ``path`` into ``os.environ``.

    Variables already present in the process environment always win, so a
    deployment's real environment can never be overridden by a stray file.
    Supports blank lines, ``#`` comments and optionally quoted values; it
    intentionally does not support interpolation or multi-line values.
    """
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def env_str(name: str, default: str | object = _MISSING) -> str:
    value = os.environ.get(name)
    if value is None or value == "":
        if default is _MISSING:
            raise ImproperlyConfigured(f"Required environment variable {name} is not set.")
        return str(default)
    return value


def env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    normalized = value.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise ImproperlyConfigured(f"Environment variable {name} must be a boolean, got {value!r}.")


def env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ImproperlyConfigured(
            f"Environment variable {name} must be an integer, got {value!r}."
        ) from exc


def env_list(name: str, default: list[str] | None = None) -> list[str]:
    """Parse a comma-separated variable into a list of non-empty items."""
    value = os.environ.get(name)
    if value is None or value == "":
        return list(default or [])
    return [item.strip() for item in value.split(",") if item.strip()]
