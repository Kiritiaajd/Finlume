# Testing Strategy

Finlume's results inform financial decisions, so correctness is a product
feature, not just an engineering preference. This document defines what we
test, at which layer, and how.

Related: [QUALITY_GATES.md](../development/QUALITY_GATES.md), [FINANCIAL_CALCULATION_CONVENTIONS.md](../data/FINANCIAL_CALCULATION_CONVENTIONS.md), [ADR-0003](../decisions/ADR-0003-deterministic-calculation-engine.md).

## 1. Principles

1. **Hand-verified expectations.** Expected financial values are calculated independently (by hand, in a spreadsheet, or from a published source) and written as exact `Decimal` strings. Never derive a test's expected value by calling the code under test.
2. **Edge cases are the main cases.** Missing values, zero, negative values, rounding midpoints, very large numbers and mixed scales get explicit tests.
3. **Fictional data only.** Fixtures, golden files and screenshots use invented companies and figures. Real financial records, real people and real account numbers never enter the repository.
4. **Deterministic tests.** No network access, no wall-clock dependence, no random data without a fixed seed.
5. **Fast feedback.** Domain tests need no database or Django request cycle, so most of the suite runs in about a second.
6. **Strict by configuration.** pytest runs with `--strict-markers`, `--strict-config`, and `filterwarnings = error`: a new deprecation warning fails the build.

## 2. Test pyramid

```text
                 ┌──────────────────────┐
                 │  End-to-end (web)    │  Playwright: critical user journeys (Phase 1)
                 ├──────────────────────┤
                 │  API tests           │  DRF APIClient: status, envelope, auth, scoping
                 ├──────────────────────┤
                 │  Integration         │  ORM + PostgreSQL: constraints, migrations, Decimal round-trips
                 ├──────────────────────┤
                 │  Domain unit tests   │  Pure Python: calculations, validation, units (the bulk)
                 └──────────────────────┘
        Cross-cutting: architecture rules · settings safety · migration drift · security
```

| Layer | Location | Database | What it proves |
|---|---|---|---|
| Domain unit | `backend/tests/domain/` | none | Formulas, rounding, sign conventions, missing-data behaviour, determinism |
| Architecture | `backend/tests/test_architecture.py` | none | `domain/` imports nothing from Django, DRF, `apps`, `config`, `infrastructure`, `psycopg` or `requests` |
| Configuration | `backend/tests/config/` | none / test DB | Environment parsing; production settings refuse unsafe configuration; models and migrations in sync |
| Infrastructure | `backend/tests/infrastructure/` | none | Private storage never yields URLs; location check `finlume.E001` |
| Model / integration | `backend/tests/accounts/` (more per app in Phase 1) | test DB | Constraints (e.g. case-insensitive unique email), defaults, `public_id` |
| API | `backend/tests/api/` | test DB | Routing and versioning, error envelope, authentication defaults, request IDs, health semantics |
| Frontend unit / component | `apps/web` (Phase 1) | n/a | Rendering, formatting of string decimals, form validation |
| End-to-end | `apps/web` (Phase 1) | full stack | Enter or upload a statement, run an analysis, view the dashboard |

## 3. Current suite (Phase 0)

126 tests across thirteen modules. Counts are from `pytest --collect-only`; parametrised cases count separately.

| Module | Tests | Covers |
|---|---|---|
| `tests/test_architecture.py` | 14 | Domain dependency rule, one case per `domain/` file |
| `tests/api/test_health.py` | 7 | 200/503 semantics, no error leakage, `no-store`, generated / propagated / rejected request IDs, request ID kept on 4xx log lines, unknown API version → JSON 404 |
| `tests/api/test_security_defaults.py` | 4 | Views with no policy of their own: anonymous → 403 `not_authenticated`, authenticated → 200, session POST without CSRF token → 403, pagination default 50 and cap 200 |
| `tests/api/test_error_envelope.py` | 9 | Envelope shape and codes, Django exception mapping, parser internals hidden, unexpected errors propagate |
| `tests/accounts/test_user_model.py` | 3 | Custom user model active, distinct `public_id`, case-insensitive unique email |
| `tests/config/test_env.py` | 9 | `.env` parsing never overrides the real environment; typed getters fail loudly |
| `tests/config/test_settings.py` | 8 | Valid production config loads; missing or short secret, missing hosts, SQLite and missing DB password are rejected; production hardening flags; `makemigrations --check` |
| `tests/config/test_database_settings.py` | 11 | Database selection without connecting:<br>• development defaults to PostgreSQL;<br>• missing `POSTGRES_*` are listed, with no SQLite fallback;<br>• explicit SQLite opt-in and warning `finlume.W001`;<br>• unknown engines rejected;<br>• test settings follow `FINLUME_TEST_DB_ENGINE` only;<br>• production still PostgreSQL |
| `tests/core/test_dbstatus.py` | 5 | `manage.py dbstatus`: up-to-date, pending migrations (exit 3, nothing applied) and unreachable (exit 2) cases; the target description never contains the password |
| `tests/infrastructure/test_private_storage.py` | 6 | Save/open round trip, `url()` raises, configured storages are private, location check |
| `tests/domain/test_financial_statements.py` | 22 | Exact scale normalisation (incl. lakhs and crores, very large values), Decimal-only and finite-only inputs, currency codes, periods, immutable fact sets |
| `tests/domain/test_validation.py` | 8 | Balance sheet identity within / beyond tolerance, gross profit subtotal, sign convention, no mutation |
| `tests/domain/test_calculations.py` | 20 | Hand-calculated ratios, half-even rounding at a midpoint, independence from the caller's decimal context, missing / zero / negative denominators, out-of-range results reported rather than raised (including round-up to the bound and context overflow), determinism and engine version |

Production-settings tests run `import config.settings.production` in a
subprocess with an explicit environment. Explicit empty values override any
local `.env`, so results do not depend on the developer's machine.

## 4. Financial calculation testing

Every metric and validation rule must have:

1. **A hand-calculated happy path** with a short comment showing the arithmetic when it is not obvious.
2. **Missing-input cases.** The result is `value = None` with `missing_input`, never zero.
3. **A zero-denominator case.** The result is `value = None` with `zero_denominator`; no exception and no infinity.
4. **Negative cases.** Losses, negative equity and cash outflows, with the expected issue codes.
5. **Rounding cases.** A value on an exact half-even midpoint at the sixth decimal place, and a repeating decimal (e.g. 1/3).
6. **Scale and magnitude cases.** Values normalised from thousands, lakhs, millions, crores and billions, and figures above 10¹⁸.
7. **A context-independence check.** The result is unchanged when the caller's ambient `decimal` context has low precision.

**Property-style checks** (added as the engine grows) assert invariants
instead of single values. Examples:

- Normalisation is exact and reversible.
- Validation never mutates inputs.
- Repeated runs produce identical outcomes.
- Scaling all inputs of a ratio by the same factor leaves the ratio unchanged.

Hypothesis may be introduced for these when the value justifies the extra
dependency.

**Golden-file regression fixtures (Phase 1).** A versioned set of fictional
company statements (YAML or CSV under `backend/tests/fixtures/`) with expected
outputs for every metric and issue at the current `ENGINE_VERSION`. Any change
to a golden output must come with an `ENGINE_VERSION` bump and a `CHANGELOG.md`
entry (see [the PR template](../../.github/PULL_REQUEST_TEMPLATE.md)).

## 5. Database and integration testing

- **Local default:** pytest uses SQLite in memory (`config.settings.test`) for fast, isolated runs. The test database is chosen by `FINLUME_TEST_DB_ENGINE`, independently of the development database, which defaults to PostgreSQL. A local suite run therefore never touches your PostgreSQL server unless you ask for it.
- **CI is authoritative:** the `backend` job sets `FINLUME_TEST_DB_ENGINE=postgresql` and `FINLUME_REQUIRE_POSTGRES_TESTS=1`, and runs the whole suite against a PostgreSQL 17 service container. The guard makes pytest fail outright if it would run on anything else. SQLite does not preserve decimal precision like PostgreSQL `numeric` and differs in constraint behaviour, so a passing local SQLite run is not sufficient for persistence code.
- **Locally against PostgreSQL:** start `docker compose up -d db`, then run `pytest` with `FINLUME_TEST_DB_ENGINE=postgresql` and the `POSTGRES_*` variables from `.env` ([LOCAL_SETUP.md](../development/LOCAL_SETUP.md#5-run-the-checks)).
- **Settings tests** (`tests/config/test_database_settings.py`) pin the selection rules without connecting to any database:
  - development defaults to PostgreSQL and fails with every missing variable listed;
  - SQLite is used only when explicitly selected, with warning `finlume.W001`;
  - test settings ignore the development engine;
  - production still requires PostgreSQL.
- **The `postgres` marker** (`@pytest.mark.postgres`) labels tests that need PostgreSQL-specific behaviour, such as `numeric` precision or partial indexes. Such tests must skip cleanly on SQLite.
- **Phase 1 persistence tests** must cover a `Decimal` round trip at full declared precision, unique and check constraints, workspace-scoped queryset helpers, and immutability of saved analysis runs.
- **Migrations:** `makemigrations --check --dry-run` runs in CI, locally (`scripts/check.*`) and inside the suite. Data migrations get dedicated tests that apply them to representative fictional data.

## 6. API testing

For every endpoint (Phase 1 onwards):

- success status and response shape, with decimals serialised as strings;
- `validation_error` with field-level `details` for invalid input;
- unauthenticated access is rejected;
- **a cross-workspace access attempt returns 404** (IDOR guard);
- role checks (viewer cannot write, editor cannot manage members);
- CSRF is enforced for session-authenticated unsafe methods (use `APIClient(enforce_csrf_checks=True)`);
- pagination parameters and the `max_page_size` cap where lists are returned.

## 7. Security testing

| Check | Where | Status |
|---|---|---|
| Unsafe production configuration rejected | `tests/config/test_settings.py` | Implemented |
| Private storage cannot produce public URLs; location check | `tests/infrastructure/` | Implemented |
| Error responses leak no internals | `tests/api/test_error_envelope.py`, `test_health.py` | Implemented |
| Request ID log-injection guard | `tests/api/test_health.py` | Implemented |
| Static security lint (Ruff `S` rules, bandit-derived) | CI `backend` job | Implemented |
| Dependency vulnerabilities (`pip-audit`) | CI `dependency-audit` job, `scripts/check.*` | Implemented |
| `manage.py check --deploy` with production settings | Release checklist | Documented; automate before the first release |
| Authorization matrix and cross-workspace tests | API tests | Planned (Phase 1) |
| Upload abuse (oversized, wrong type, path names, CSV formula export escaping) | Ingestion tests | Planned (Phases 1–2) |
| Secret scanning (e.g. GitHub secret scanning or gitleaks) | Repository / CI | Planned |

## 8. Frontend testing

**Web (implemented):** Vitest + React Testing Library in jsdom, with 28 tests in five files
under `apps/web/src`:
- the Zod form resolver;
- the API client's failure classification;
- exact string-decimal formatting;
- the synthetic sample data's internal consistency, checked with integer arithmetic;
- routing, empty, unavailable and sample states;
- the settings form.

`npm run check` adds `tsc -b`, ESLint and the production build. CI runs it.

**Mobile (implemented):** `tsc --noEmit`, `expo-doctor` and a Metro bundle export. There are
no component tests yet.

**Planned:**

| Tool | Scope |
|---|---|
| **Vitest** | Unit tests for formatting (string decimals, never `parseFloat` for money), API client helpers, Zod schemas |
| **React Testing Library** | Component behaviour and accessibility queries (by role and label) |
| **Mock Service Worker** (optional) | Contract-shaped API mocks for component tests |
| **Playwright** | End-to-end journeys against a running backend with fictional seed data, plus automated accessibility checks (axe) on key pages |
| TypeScript `tsc --noEmit` and ESLint | Static gates in CI |

The mobile app (React Native + Expo) will use Jest with React Native Testing
Library when it is introduced.

## 9. Coverage expectations

- **`domain/`:** 100 % line and branch coverage is the target. Every uncovered branch in calculation code needs a justification in review.
- **Overall backend:** at least 90 % branch coverage. The current suite measures **90 %**, excluding migrations and ASGI/WSGI entry points. Production settings are exercised in subprocesses, which line coverage does not count.
- Coverage is a floor, not a goal. A covered line without a meaningful assertion does not count in review.
- A CI coverage threshold (`--cov-fail-under`) will be enabled once Phase 1 code lands and the baseline stabilises.

## 10. Running the tests

From `backend/` with the virtual environment active:

```bash
python -m pytest                          # whole suite (SQLite in memory)
python -m pytest tests/domain -q          # domain only, no database
python -m pytest --cov                    # with branch coverage report
python -m pytest -m postgres              # PostgreSQL-only tests (requires FINLUME_TEST_DB_ENGINE=postgresql)
```

Or run every gate CI runs: `scripts/check.ps1` (Windows) or `scripts/check.sh` (macOS/Linux).
