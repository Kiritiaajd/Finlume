# Quality gates

Every pull request must pass these gates. Run them locally with
[`scripts/check.ps1`](../../scripts/check.ps1) or
[`scripts/check.sh`](../../scripts/check.sh) from an activated virtual environment.
CI runs the same gates in [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml).

All commands run in `backend/`.

| Gate | Command | Fails when |
|------|---------|------------|
| Formatting | `python -m ruff format --check .` | Any file is not Ruff-formatted. Fix with `python -m ruff format .`. |
| Lint | `python -m ruff check .` | Ruff rules fail. The rule set covers pycodestyle, pyflakes, isort, bugbear, pyupgrade, bandit-derived security checks (`S`), Django (`DJ`), naive datetimes (`DTZ`), pytest style and more. Configured in `pyproject.toml`. |
| Type check | `python -m mypy .` | `strict = true` with the django-stubs and DRF plugins finds an error. Tests relax untyped-definition rules only. |
| Django checks | `python manage.py check --fail-level WARNING --settings=config.settings.test` | Any system check warns, including `finlume.E001` (private storage inside a public directory). |
| Migrations | `python manage.py makemigrations --check --dry-run --settings=config.settings.test` | Models changed without a migration. |
| Tests | `python -m pytest --cov` | A test fails or emits a warning (`filterwarnings = error`). |
| Dependency audit | `python -m pip_audit -r requirements/base.txt` (CI also audits `requirements/dev.txt`) | A dependency has a known vulnerability. |
| Lock consistency (CI only) | Re-compiles both lock files over copies of themselves and diffs the result | `pyproject.toml` and `requirements/*.txt` disagree. |

## Test layers

| Layer | Location | What it proves |
|-------|----------|----------------|
| Domain unit tests | `tests/domain/` | Calculations, normalisation and validation are exact and deterministic. No database is involved. |
| Architecture test | `tests/test_architecture.py` | `domain/` never imports Django, DRF, `apps`, `config`, `infrastructure`, `psycopg` or `requests`. |
| Integration tests | `tests/accounts/`, `tests/infrastructure/` | Models, constraints and storage behave correctly against a real database or filesystem. |
| API tests | `tests/api/` | HTTP status codes, the error envelope, request IDs and public/private access. |
| Configuration tests | `tests/config/` | Production settings refuse unsafe configuration; the environment parser fails loudly. |

The full strategy is in [TESTING_STRATEGY](../architecture/TESTING_STRATEGY.md).

## Database used by tests

- The test database is chosen by `FINLUME_TEST_DB_ENGINE`, independently of the development database (`FINLUME_DB_ENGINE`). Local runs default to SQLite in memory. With `FINLUME_TEST_DB_ENGINE=postgresql` they use the `POSTGRES_*` server, creating and dropping `test_<POSTGRES_DB>`.
- CI runs the suite on PostgreSQL 17 for Python 3.10 and 3.13 (`FINLUME_TEST_DB_ENGINE=postgresql`), and **a PR is green only if the PostgreSQL run passes**. `FINLUME_REQUIRE_POSTGRES_TESTS=1` makes pytest refuse to run there on any other database.
- Tests that depend on PostgreSQL-specific behaviour must be marked `@pytest.mark.postgres`.

## Security checks

- Ruff's `S` rules catch common insecure patterns statically.
- `pip-audit` checks locked dependencies against known advisories.
- `python manage.py check --deploy` (run with production settings and real environment values) must report nothing except deliberate, documented exceptions. Today the only exception is `security.W004` (HSTS), which operators enable once HTTPS is confirmed.
- Tests assert that error responses never leak internal exception text.

## Current baseline (2026-10-25, Windows, Python 3.10.7)

| Gate | Result |
|------|--------|
| Ruff format / lint | Clean |
| mypy (strict) | No issues in 69 source files |
| `manage.py check` | No issues |
| `makemigrations --check` | No changes |
| pytest | 126 passed, 0 skipped, 90 % branch coverage (SQLite; PostgreSQL run pending) |
| pip-audit, runtime | No known vulnerabilities |
| pip-audit, dev on Python 3.10 | `filelock` 4.1.0 advisories. The package is development-only and transitive (via pip-audit), and its fix needs Python ≥ 3.11. Not present on the 3.13 CI audit. |
| `check --deploy` | `security.W004` only, by design |

The PostgreSQL CI run has not executed yet. It will run on the first push to GitHub.

## Frontend gates

| App | Local command | CI job |
|---|---|---|
| `apps/web` | `npm run check` (typecheck, ESLint, Vitest, production build); `npm audit` | `web` |
| `apps/mobile` | `npm run typecheck`, `npm run doctor`, `npm run bundle:check` | `mobile` (typecheck and doctor) |

Details and current results: [Frontend applications](FRONTEND.md).

## Coverage

Coverage is measured with branch coverage over `config`, `apps`, `domain` and `infrastructure`, excluding migrations and the ASGI/WSGI entry points. There is no hard threshold yet. Domain calculation code is expected to stay at 100 %, and any coverage drop must be explained in review.
