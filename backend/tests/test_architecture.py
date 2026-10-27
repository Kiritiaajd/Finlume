"""Guards the dependency direction described in DOMAIN_BOUNDARIES.md."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
DOMAIN_DIR = BACKEND_DIR / "domain"
SERVICES_DIR = BACKEND_DIR / "services"

FORBIDDEN_IN_DOMAIN = (
    "django",
    "rest_framework",
    "apps",
    "services",
    "config",
    "infrastructure",
    "psycopg",
    "requests",
)

# Use cases never see HTTP: no DRF requests, serializers or exceptions.
FORBIDDEN_IN_SERVICES = ("rest_framework",)


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module)
    return modules


@pytest.mark.parametrize(
    "path", sorted(DOMAIN_DIR.rglob("*.py")), ids=lambda p: str(p.relative_to(BACKEND_DIR))
)
def test_domain_does_not_depend_on_frameworks_or_outer_layers(path: Path) -> None:
    violations = {
        module for module in _imported_modules(path) if module.split(".")[0] in FORBIDDEN_IN_DOMAIN
    }
    assert not violations, f"{path.name} imports {sorted(violations)}"


@pytest.mark.parametrize(
    "path", sorted(SERVICES_DIR.rglob("*.py")), ids=lambda p: str(p.relative_to(BACKEND_DIR))
)
def test_services_do_not_depend_on_the_api_layer(path: Path) -> None:
    violations = {
        module
        for module in _imported_modules(path)
        if module.split(".")[0] in FORBIDDEN_IN_SERVICES
    }
    assert not violations, f"{path.name} imports {sorted(violations)}"
