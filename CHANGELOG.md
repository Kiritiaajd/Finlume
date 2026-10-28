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

- `.github/dependabot.yml`: weekly update pull requests for the backend (pip), the web client (npm) and GitHub Actions, and security updates only for the mobile client. Django and its type stubs stay on their current LTS lines.
- ADR-0007, *Authentication, sessions and login protection for the MVP*: `401` with a `Session` challenge for unauthenticated requests, email sign-in, sessions that expire after 8 hours of inactivity, and built-in login throttles (5/minute per IP and per email). It is to be implemented in MVP step 1.
- The approved retention defaults (D-07) and the `workspaces` app name (FA-26) are recorded in the architecture decisions.
- ADR-0008, *Organizations and workspace tenancy* (proposed), and `docs/development/TENANCY_IMPLEMENTATION_PLAN.md`, which together specify MVP step 1:
  - organizations as the customer boundary;
  - a private personal workspace per user;
  - access only through workspace membership, also for organization admins;
  - one access check per request;
  - last-owner and last-admin rules;
  - operator-only ownership recovery;
  - teams deferred.

  The data model, domain boundaries, product scope (FR-003 to FR-005, acceptance criterion 2), API conventions (every tenant resource nested under its workspace; `409 conflict`), data lifecycle and MVP plan are updated to match.
- Scaffold for MVP step 1. It adds docstring-only modules plus configuration, and no behaviour yet:
  - `backend/services/` is the application layer, holding business workflows with one sub-package per capability. The tenancy capabilities `access`, `accounts`, `organizations` and `workspaces` exist now. `statement_analysis`, `documents`, `stock_research` and `portfolio_analysis` are created with their first feature (DOMAIN_BOUNDARIES §3.3).
  - The new Django apps `organizations`, `workspaces` and `audit` are registered in `INSTALLED_APPS`. Their URL modules are included in `/api/v1/` with no routes yet.
  - Placeholder modules for the authentication work in `accounts`.
  - New test packages.
  - `services` is added to Ruff's first-party packages and to the coverage sources.
  - `tests/test_architecture.py` now also forbids `services` imports in the domain and DRF imports in `services`.

- **Tenancy models (MVP step 1a, ADR-0008):**
  - `Organization` and `OrganizationMembership` (`admin` or `member`).
  - `Workspace`: exactly one of `organization` and `personal_owner` is set, enforced by a CHECK constraint.
  - `WorkspaceMembership` (`owner`, `editor` or `viewer`), unique per user and workspace.
  - Role CHECK constraints on both membership tables.
  - The abstract `PublicModel`, which holds the standard columns.
- **Data migration** `workspaces.0002`: it gives every existing user a personal workspace and owner membership. It runs in batches and is idempotent.
- **`services.access`:** `require_workspace_role` and `require_organization_role`. Each takes one indexed query. A non-member gets `404` and a role that is too low gets `403`. Organization admins get no implicit workspace access.
- **`services.errors.ConflictError`**, returned by the API as `409 conflict` with its safe message.
- **Read-only admin** for the four tenancy models (`apps.core.admin.ReadOnlyModelAdmin`). Users can no longer be deleted from the admin (ADR-0008 §7).

- **Authentication (MVP PR 1b, ADR-0007):**
  - API sign-in is by email, case-insensitive, through `EmailBackend`, which uses the existing expression index. `ModelBackend` stays for the Django admin.
  - New endpoints: `GET auth/csrf/`, `POST auth/register/`, `POST auth/login/`, `POST auth/logout/` and `GET me/`. Registration and sign-in are CSRF-checked.
  - Registration creates the user, their personal workspace and the owner membership in one transaction. A duplicate email returns `409`.
  - The first sign-in provisions a missing personal workspace, for example for an account created with `createsuperuser`.
  - Sign-in is throttled to 5 attempts per minute per IP and per email (`FINLUME_THROTTLE_LOGIN_IP`, `FINLUME_THROTTLE_LOGIN_EMAIL`).
  - Sessions expire after 8 hours of inactivity and are renewed on each request (`FINLUME_SESSION_AGE_SECONDS`).
  - A new database constraint requires a non-blank email (`accounts.0002`).
- **Audit app:** `AuditEvent`, which is append-only and carries a pseudonymous `actor_label` and the request ID, plus `AuditEvent.record()`. Registration, sign-in and failed sign-in are recorded. A failed sign-in keeps only the normalised email, never the password.

- **Workspace API (MVP PR 1c, ADR-0008):**
  - New endpoints: `GET, POST workspaces/`, `GET, PATCH workspaces/{id}/`, `GET, POST workspaces/{id}/members/` and `PATCH, DELETE workspaces/{id}/members/{user_id}/`. Viewers read, owners rename the workspace and manage its members, and any member may leave. A non-member gets `404`, including an organization admin.
  - `WorkspaceScopedView` authorizes each request with one indexed query and scopes querysets to the workspace. Every later tenant view inherits it.
  - Creating a workspace requires organization membership and makes the creator its owner in the same transaction (I5).
  - Only active members of the workspace's organization can be added (I2, I6). Personal workspaces take no other members.
  - A workspace always keeps at least one owner (I3). Concurrent demotions are serialised by a row lock.
  - `python manage.py recover_workspace_owner <workspace_id> <email> --reason "…"`: operator-only ownership recovery, allowed only when every owner's account is inactive, and always audited as `workspace.ownership_recovered`. There is no API for it.
  - Events `workspace.created`, `workspace.renamed`, `membership.added`, `membership.role_changed` and `membership.removed` are audited.
  - Query budgets for the workspace endpoints are enforced by the `assert_app_queries` test fixture.

- **Organization API (MVP PR 1d, ADR-0008):**
  - New endpoints: `GET, POST organizations/`, `GET, PATCH organizations/{id}/`, `GET, POST organizations/{id}/members/` and `PATCH, DELETE organizations/{id}/members/{user_id}/`. Members read and admins write. Any member may leave, and a non-member gets `404`.
  - Any signed-in user can create an organization and becomes its admin.
  - Admins add existing, active accounts by email. Because this reveals whether an address is registered, it is throttled per user (30/hour, `FINLUME_THROTTLE_ORGANIZATION_MEMBER_ADD`).
  - An organization always keeps at least one admin (I4). Concurrent demotions are serialised by a row lock.
  - Removing a member, or a member leaving, also removes their memberships in the organization's workspaces, in the same transaction (I2). This is refused while they are the last owner of one of those workspaces.
  - Adding a workspace member and creating a workspace now lock the user's organization membership, so a concurrent removal from the organization cannot leave a workspace membership behind.
  - Events `organization.created`, `organization.renamed`, `organization.member_added`, `organization.member_role_changed` and `organization.member_removed` are audited.
  - `tests/test_tenant_isolation.py` holds the plan's §8 security tests, parametrized over every tenancy endpoint. PostgreSQL concurrency tests cover the last-admin rule and the workspace-membership sync.

- **Financial statement models (MVP step 2a, DATA_MODEL §4.4 to 4.8):** no API yet; statement entry arrives in step 3.
  - New apps `financial_records` (`ReportingEntity`, `FinancialStatement`, `StatementLineItem`, `FinancialFact`) and `documents` (`SourceDocument`, `manual_entry` only; file columns arrive with CSV import in step 4).
  - Statement types, period types, scales and line-item codes come from `domain.financial_statements`, so the database accepts exactly the engine's taxonomy.
  - Versioned statements: `UNIQUE (entity, statement_type, period, version)`; at most one validated and at most one draft version per statement and period (partial unique indexes); `(version = 1) = (supersedes IS NULL)`; and a restatement reason (not only whitespace) exactly when restating.
  - Version *n* can restate only version *n − 1* of the same statement (`financial_records.0003`, using the generated column `previous_version`), so a restatement chain cannot loop, skip or run backwards.
  - CHECK constraints for every code, the currency format (`^[A-Z]{3}$`), `period_start <= period_end`, positive versions and row numbers, and the fiscal month (1–12). A line-item code is mapped at most once per statement, in both raw rows and facts.
  - Provenance links (fact → statement, fact → raw row, statement → entity, statement → source document, statement → restated version) are `RESTRICT`; deleting a whole workspace still cascades through all of them.
  - On PostgreSQL, composite foreign keys (`financial_records.0002` and `0003`) keep a statement's entity, source document and restated version in its workspace, keep each fact's workspace, entity, period and currency equal to its statement's, and tie each fact to a mapped row of its own statement.
  - Read-only admin for the five models.

- **Statement mapping and assembly (MVP step 2b, rule A2 approved):** `services/statement_analysis/`, the first financial capability. No API yet; step 3 and step 5 call it.
  - `assemble_analysis_input(entity=…, period=…)` builds the engine's `FinancialFactSet` for one entity and period, from the **validated** version of each statement type and its **confirmed** facts, in two queries. Drafts, superseded versions, other periods, period types, entities and workspaces are never used. A missing statement type is allowed, and the engine reports its ratios as `missing_input`. It also returns the exact statements and facts used, for step 5's run records.
  - Statements in different currencies, or no validated statement for the period, are refused with `ConflictError` (`409 conflict`), naming the currency codes but no amounts.
  - `build_facts(statement, review_status=…)` turns a statement's mapped raw rows into unsaved facts in base units, scaled exactly with `domain.financial_statements.normalize_amount`. Unmapped rows and blank cells give no fact, signs are never flipped, a code from another statement type is refused, and so is a value too large for `numeric(30,6)` once scaled (FA-15).

- **Manual statement entry, drafts (MVP step 3a):** the first endpoints for financial data, all under `/api/v1/workspaces/{ws}/` and behind the one-query workspace check. Viewers read; editors write.
  - `GET/POST entities/` and `GET entities/{id}/`: reporting entities, with a unique name per workspace (`409` on a duplicate).
  - `GET/POST entities/{id}/statements/`: every version of an entity's statements, and a new **draft** (version 1) with its raw rows and a manual-entry source document.
  - `GET/PATCH statements/{id}/`: one statement with its rows. Only a draft can be edited; sending `line_items` replaces all rows; a restatement draft keeps its statement type and period. A statement already existing for the period is a `409`.
  - Input validation answers field-level `400`s: amounts only as decimal strings (JSON numbers refused), at most 6 decimal places, below 10²⁴ as entered and once scaled (FA-15), a line-item code only on its own statement type and once per statement, and at most 500 rows. The exact text sent is kept as `raw_value`.
  - An entity or statement ID from another workspace answers `404`.
  - `GET /api/v1/line-items/`: the taxonomy with each code's statement type, sign convention and definition, as help text for entry forms.
  - Events `entity.created`, `statement.created` and `statement.updated` are audited, without amounts.
- **API contract (MVP step 6):** the v1 API now has an OpenAPI 3 schema, and the web client typed from it.
  - **Schema:** `docs/api/openapi-v1.yaml`, generated by `drf-spectacular` (new runtime dependency, recorded in ADR-0004). Every operation documents its request, its success response and the error envelope for `4XX` and `5XX`, with readable operation IDs and one named enum per choice set.
  - **`GET /api/v1/schema/`** is for signed-in users only. drf-spectacular's own default is `AllowAny`; the schema view takes DRF's project authentication and permission classes instead, and errors use the JSON envelope. Tests cover anonymous (`401` with the `Session` challenge), signed-in, and the view's classes.
  - **Contract tests:**
    - the committed YAML must equal the generated schema, which must validate and generate without warnings;
    - real responses are checked against their documented schemas, with undocumented keys refused (`tests/api/contract.py`).
  - **Every endpoint, from the URL resolver:** a test walks Django's registered routes, not a hand-kept list. It checks that every route is documented; that every non-public endpoint answers `401` to anonymous callers; and that every endpoint answers `404` both to outsiders and to IDs from another workspace or organization. A new route parameter without a recipe fails the test instead of being skipped.
  - **End to end:** one test walks MVP acceptance criteria 1 to 10 through the API, with real registration and CSRF enforced, checking every response against the contract. Pagination and ordering rules are tested too.
  - **Coverage floor:** `fail_under = 85` (FA-23); coverage is 96.8%.
  - **TypeScript types:** `apps/web/src/api/generated/`, generated with `@hey-api/openapi-ts` (types only, pinned exactly). `npm run api:types:check`, the first step of `npm run check`, fails when they are out of date with the committed YAML. An npm override moves its nested `js-yaml` to 4.3.2, which fixes high-severity advisories.
- **Fixed: reviewing an imported mapping lost the CSV's original text.** Replacing every row with `PATCH statements/{id}/` overwrote each row's `raw_value`. The new `PATCH statements/{id}/line-items/{row_id}/` `{"line_item_code"}` changes only a draft row's code; its amount, original text and source line stay as read (FR-014). `statement.row_mapped` is audited.
- **Saved reports (MVP step 5b):** step 5 is complete.
  - `GET/POST workspaces/{ws}/reports/` and `GET/PATCH reports/{id}/`: a title, the user's notes and an ordered list of up to 50 runs. Viewers read; editors write, and `run_ids` replaces the whole list.
  - A report stores no figures. It is rendered live from its immutable runs, with each run's metrics, issues and `uses_superseded_statement`, so it can never drift from them. A report costs 5 queries however many runs it lists.
  - New `reports` app: `Report` and `ReportRun` (`RESTRICT` on the run, unique run and position per report), with PostgreSQL composite keys so a report only lists runs of its own workspace. A run ID that is unknown or from another workspace gets the same `400`. Read-only admin; `report.created` and `report.updated` are audited without figures.
  - `AnalysisRun` gains a `(workspace, id)` key (`analysis.0003`) for those composite keys. The "statement restated since" flag is now one shared query helper, `with_superseded_flag`.
- **Analyses (MVP step 5a):** run, save and reload immutable analyses (acceptance criteria 6 and 7).
  - `POST workspaces/{ws}/entities/{id}/analyses/` (editor) with a period assembles that period's validated statements (rule A2), runs the engine and saves the run, all seven metrics with their methodology and inputs, every issue and the exact facts used, in one transaction. `GET entities/{id}/analyses/` and `GET analyses/{id}/` read them (viewer).
  - Every run is new and immutable: the model refuses updates and single deletions (`ImmutableRecordError`), and there is no endpoint for either. Running again on unchanged inputs gives the same fingerprint and values. A missing input is `null` with a `missing_input` issue, never zero.
  - No validated statement for the period, or mixed currencies, is a `409`, and nothing is saved. `Idempotency-Key` replays return the original run.
  - Each run lists its inputs traced to row, statement version and document (criterion 9), and `uses_superseded_statement` flags runs whose statements were later restated.
  - New `analysis` app: `AnalysisRun`, `MetricResult` (`numeric(24,6)`), `AnalysisIssue` and the input-fact join (`RESTRICT`, so used facts can never be deleted), with CHECKs on every code, a PostgreSQL composite key keeping a run's entity in its workspace, and a read-only admin. `analysis.run` is audited with counts only, no figures.
  - **Input fingerprint (FA-11 fixed):** `domain.calculations.fingerprint`, the canonical SHA-256 from the calculation conventions §10, with a golden-value test. More than 6 decimal places is refused, never rounded.
  - The `Idempotency-Key` header parsing moved to `api/idempotency.py`, shared by imports and analyses.
- **CSV statement import (MVP step 4):** `POST workspaces/{ws}/entities/{id}/imports/` (multipart, editor).
  - The CSV becomes a **draft** statement. Each row carries a proposed code: from the file's optional `code` column, otherwise an exact name match (no fuzzy guessing). The user reviews it with `PATCH` and creates the facts with step 3's `validate` (FR-013, FR-014, acceptance criterion 4).
  - The format is strict and documented: `label`, `amount` and optionally `code`. Amounts are read exactly, never through a float; `(1,234.56)` is negative, and comma grouping is accepted, including Indian. The cell text is kept as `raw_value`, and each row records its file line (`line 7`), so every fact traces to its line, statement version and document (criterion 9). New pure parsing rules live in `domain/financial_statements/csv_import.py`.
  - All or nothing: every file and row problem is reported at once (`details.file`, `details.rows.<line>.<column>`), and on any refusal neither the file nor a row is stored. Manual entry and imports share one set of row rules (`services/statement_analysis/rows.py`).
  - Uploads are limited to 1 MiB (`FINLUME_MAX_UPLOAD_BYTES`, new `413 payload_too_large`) and 500 rows (`FINLUME_MAX_IMPORT_ROWS`). An oversized request is refused from `Content-Length` before its body is read. The upload stays in memory and never reaches a temporary file (FA-06).
  - The file is checked to be UTF-8 text by its content, fingerprinted with SHA-256 and stored privately under a random key (`services/documents/`). A re-upload of the same file gets a `duplicate_file` warning. `Idempotency-Key` replays return the original import.
  - `documents.0002` adds the `csv_upload` kind, the file columns, a CHECK that a file has its fingerprint, size and key while manual entry has none, the per-user idempotency key and the `(workspace, sha256)` index. The read-only admin shows file metadata without any file link (FA-21).
  - Use cases can raise `services.errors.InvalidInput`, answered as `400 validation_error` with its details. The `document.uploaded` event is audited.
- **Validating and restating statements (MVP step 3b):** step 3 is complete.
  - `POST statements/{id}/validate/` turns a draft into the validated version and saves its facts in base units (`build_facts`), confirmed by the caller. Consistency warnings (`unexpected_sign`, `balance_sheet_imbalance`, `subtotal_mismatch`) are returned in `issues` and never block (acceptance criterion 5). A draft with no mapped figure is a `409`.
  - `POST statements/{id}/restatements/` `{"reason", "line_items"?}` starts version *n + 1* of the validated version as a draft, copying its rows unless new ones are sent. Version *n*, its facts and the analyses that used them stay unchanged; validating the draft supersedes version *n* (acceptance criterion 8). One restatement at a time.
  - Statuses change only by validating, which supersedes exactly the version being restated, before validating the new one. Both actions lock the validated version, then the draft, so concurrent requests queue (PostgreSQL concurrency tests).
  - `GET statements/{id}/` now includes the statement's facts, each linked to its source row.
  - Events `statement.validated` and `statement.restated` are audited, without amounts.
- **Line-item definitions (decision A4, FA-10 approved):** `LineItem.definition` for all 21 codes. Debt excludes lease liabilities; equity and net income both include non-controlling interests; operating income is as reported. Formulas and `ENGINE_VERSION` are unchanged.

### Changed

- **Unauthenticated API requests now get `401`** with `WWW-Authenticate: Session`, instead of `403`. Signed-in users without permission, and CSRF failures, still get `403`.
- `User.__str__` returns the email address.
- Ruff's `S105` and `S106` rules (hard-coded passwords) are not applied to tests, because fixture passwords are fictional.
- **API layout:** shared DRF plumbing moved from `apps/core` to a new `backend/api/` package (`api.exceptions`, `api.pagination`). Each app's endpoints now live in its own `apps/<app>/api/` package. The architecture test forbids `api` imports in `domain` and in `services`.
- **Python 3.12 is now the minimum** (was 3.10, which reaches end of life in October 2026). `requires-python`, the Ruff and mypy targets, and the lock files now use 3.12. CI tests 3.12 and 3.13. The re-lock only dropped the pins for Python below 3.11, which removes the development-only `filelock` 4.1.0 advisory. **Recreate an existing `.venv`** on 3.12 or 3.13 ([Local setup](docs/development/LOCAL_SETUP.md#python-versions)).
- `LineItem` and `IssueCode` are now `StrEnum`. Their values are unchanged, and `str(member)` now returns the value. Engine output is unchanged, so `ENGINE_VERSION` stays 0.1.0.
- CI actions moved to their Node 24 majors: `actions/checkout@v5`, `actions/setup-python@v6` and `actions/setup-node@v5`.
- The web client is back on **TypeScript 6.0** (`~6.0.3`). The TypeScript 7.0.2 update broke `npm ci` with `ERESOLVE`, because `typescript-eslint` 8, including its latest release, supports only `typescript <6.1.0`. Dependabot now skips TypeScript 6.1 and later until `typescript-eslint` supports them.
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
