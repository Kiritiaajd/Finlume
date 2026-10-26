# ADR-0004: Dependency management — pyproject.toml plus hashed, uv-compiled locks

- **Status:** Accepted
- **Date:** 2026-10-25

## Context

Installs must be reproducible across Windows development machines and Linux CI, and resistant to tampered packages. The project already uses a plain virtual environment at the repository root (`.venv`). Contributors should not need extra tools just to install and run the backend.

## Decision

- [`backend/pyproject.toml`](../../backend/pyproject.toml) is the **single source of declared dependencies**: runtime in `[project].dependencies`, tooling in the `dev` extra. It also holds the Ruff, mypy, pytest and coverage configuration. The backend is not packaged (`[tool.setuptools] packages = []`).
- Lock files are generated with **uv**, which is pinned in the `dev` extra:

  ```powershell
  # in backend/
  python -m uv pip compile pyproject.toml --universal --python-version 3.10 --generate-hashes -o requirements/base.txt
  python -m uv pip compile pyproject.toml --extra dev --universal --python-version 3.10 --generate-hashes -o requirements/dev.txt
  ```

  `--universal` produces one lock with environment markers that is valid on every OS and every Python ≥ 3.10. `--generate-hashes` pins artefact hashes.
- **Installation uses plain pip**: `python -m pip install --require-hashes -r requirements/dev.txt` (or `base.txt` for runtime only). uv is needed only to re-lock.
- CI job **"Lock files match pyproject.toml"** recompiles both locks over copies of themselves, so existing pins are kept as preferences, and fails on any difference.
- `djangorestframework-stubs` stays on **3.16.x** while the runtime is DRF 3.18. The 3.18 stubs require django-stubs 6.x (Django 6), which conflicts with Django 5.2 LTS. Stubs affect type checking only.

## Consequences

### Positive
- Byte-for-byte reproducible installs, with hash verification against tampered packages.
- One lock serves Windows, macOS, Linux and Python 3.10–3.13.
- No tool beyond pip is needed to install; no second, tool-managed virtual environment.

### Negative
- Two generated files must be committed alongside `pyproject.toml`. CI enforces that they stay in sync.
- Hash-checking mode rejects ad-hoc `pip install <pkg>` into the same command. New packages must go through `pyproject.toml`.
- Slightly stale type stubs for DRF until Django 6 is adopted.

## Alternatives considered

- **pip-tools (`pip-compile`):** a workable alternative, but it locks for the current platform only and has historically broken with new pip releases.
- **Poetry:** adds its own resolver, virtualenv management and lock format, and requires every contributor to install it.
- **uv project mode (`uv sync`, `uv.lock`):** strong tooling, but it manages its own project virtual environment by default, which conflicts with the existing root `.venv` workflow, and it makes uv mandatory for installation.
- **Unpinned `requirements.txt`:** not reproducible.

## Revisit when

- The team adopts uv for all workflows. Moving to `uv.lock` is then a small change.
- The Python floor is raised. Re-lock with the new `--python-version`.
- Frontend apps arrive. They get their own JavaScript lock files (e.g. `package-lock.json`) under `apps/`.
