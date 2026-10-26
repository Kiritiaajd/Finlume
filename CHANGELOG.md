# Changelog

All notable changes to Finlume are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/). The calculation engine has its own
version (`ENGINE_VERSION`); every engine version change is listed here.

## [Unreleased]

### Added

- Architecture foundation: product scope, system design, data model,
  security, testing and governance documentation under `docs/`, plus
  architecture decision records ADR-0001 to ADR-0006.
- Django 5.2 LTS + Django REST Framework backend (`backend/`):
  - per-environment settings driven by environment variables;
  - versioned API root at `/api/v1/` and a public readiness endpoint,
    `GET /api/v1/health/`;
  - request IDs (`X-Request-ID`) and a uniform JSON error envelope;
  - custom user model with public UUID identifiers and case-insensitive
    unique email;
  - private document storage that can never produce a public URL.
- Financial domain engine, `ENGINE_VERSION` **0.1.0**: currencies, reporting
  scales, periods, the canonical line-item taxonomy, consistency checks, and
  seven ratios (gross, operating and net margin; current ratio; debt to
  equity; return on equity; return on assets).
- Test suite (pytest), lint and format (Ruff), strict type checking (mypy),
  hashed dependency locks, and a CI workflow running against PostgreSQL 17.
- Contribution, security and conduct policies, plus issue and pull-request
  templates.
- Foundation audit (`docs/architecture/FOUNDATION_AUDIT.md`) and MVP
  implementation plan (`docs/development/MVP_IMPLEMENTATION_PLAN.md`).
- Tests for project-wide API defaults: authentication required, CSRF on
  session writes, and pagination cap. Also tests for production hardening
  flags.

- Web client shell (`apps/web/`):
  - React 19, TypeScript, Vite 8, Tailwind CSS 4 (shadcn/ui conventions), TanStack Query, React Router, React Hook Form + Zod and Apache ECharts;
  - a responsive app shell with Dashboard, Financial statements, Analysis, Reports and Settings pages;
  - a typed, Zod-validated API client with a live `GET /api/v1/health/` integration, plus loading, error, degraded and API-unavailable states;
  - honest empty states with disabled actions where the backend has no API yet;
  - an optional, clearly labelled synthetic sample dashboard with interactive charts;
  - Vite `/api` proxy to Django;
  - a small local Zod resolver for React Hook Form;
  - 28 Vitest tests.
- Mobile client shell (`apps/mobile/`): Expo SDK 58, React Native 0.88 and Expo Router, with a welcome dashboard, a connection screen and a live health check configured through `EXPO_PUBLIC_API_BASE_URL`.
- CI jobs for both clients, and `docs/development/FRONTEND.md`.
- One-command development launchers: `scripts/dev.ps1` (Windows) and `scripts/dev.sh` (Linux).
  - They start Django (`127.0.0.1:8000`) and Vite (`127.0.0.1:5173`) together.
  - They check prerequisites and ports first, and stream prefixed logs, also kept in `.dev/logs/`.
  - Ctrl+C stops both process trees.
  - `-CheckOnly`/`--check` and `-Smoke`/`--smoke` modes.
  - They never install packages, migrate, or start Docker or the mobile app.
- `.gitattributes` keeps shell scripts LF on Windows checkouts.
- `python manage.py dbstatus`: a read-only command that shows the configured database (never the password), checks it is reachable and supported, and lists pending migrations. The dev launchers run it before starting: they refuse an unreachable or misconfigured database and warn about pending migrations.
- `FINLUME_TEST_DB_ENGINE` selects the test database independently of development. CI sets it to PostgreSQL, and `FINLUME_REQUIRE_POSTGRES_TESTS` makes pytest fail outright if it would run on anything else.

### Changed

- **Development now defaults to PostgreSQL.** Missing `POSTGRES_*` settings stop startup with one message listing all of them, and there is no automatic SQLite fallback. SQLite requires an explicit `FINLUME_DB_ENGINE=sqlite` and triggers warning `finlume.W001`. Production settings are unchanged.
- The Docker Compose development database and `.env.example` use host port **55432**, clear of PostgreSQL servers commonly installed on 5432/5433.

### Fixed (pre-release; engine version stays 0.1.0, see the calculation conventions)

- Ratio calculation raised `decimal.InvalidOperation` or `Overflow` for very
  large quotients, such as a tiny denominator. It now returns "not computable"
  with the new issue code `result_out_of_range`. Results are bounded below
  `1E+18` so they fit the planned `numeric(24,6)` column.
- The `missing_input` message now names every missing item with correct
  grammar.
- Log lines for 4xx responses (`django.request`) lost their request ID because
  Django writes them after the middleware has returned.
- JSON parse errors no longer echo parser internals to clients.
- Documentation no longer claims uploads are size-limited.
  `FINLUME_MAX_REQUEST_BYTES` does not cover file parts.
- The planned provenance foreign keys now use `RESTRICT` instead of `PROTECT`.
  With `PROTECT`, deleting a workspace or a user would have failed.
