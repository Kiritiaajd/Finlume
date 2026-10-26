#!/usr/bin/env bash
# Runs the same backend quality gates as CI. Usage (repository root, venv active):
#   ./scripts/check.sh
set -euo pipefail
cd "$(dirname "$0")/../backend"

step() { printf '\n==> %s\n' "$1"; }

step "Formatting";               python -m ruff format --check .
step "Lint";                     python -m ruff check .
step "Type check";               python -m mypy .
step "Django checks";            python manage.py check --fail-level WARNING --settings=config.settings.test
step "Migrations";               python manage.py makemigrations --check --dry-run --settings=config.settings.test
step "Tests";                    python -m pytest --cov
step "Runtime dependency audit"; python -m pip_audit -r requirements/base.txt --progress-spinner off

printf '\nAll checks passed.\n'
