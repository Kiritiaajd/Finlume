# MVP Implementation Plan

How Phase 1 gets built: the workflow **manual or CSV statement input → validation →
deterministic calculations → saved analysis → dashboard/report**
([product scope](../product/PRODUCT_SCOPE.md), acceptance criteria §11).

This plan follows the order agreed for the MVP. There is one justified change from the
[foundation audit](../architecture/FOUNDATION_AUDIT.md): **PostgreSQL verification moves
from step 8 to a standing prerequisite** (step 0, then a gate on every step). Every step from
step 1 on adds models with `numeric` columns, partial unique indexes and CHECK constraints
that SQLite does not reproduce (FA-03). Production hardening stays in step 8.

Decision IDs (A1–A12) refer to [FOUNDATION_AUDIT §8](../architecture/FOUNDATION_AUDIT.md#8-decisions-requiring-maintainer-approval).

## Working rules for every step

- One pull request per step, or per sub-step if it grows large. CI must be green, on PostgreSQL.
- New Django apps only when their first model or endpoint lands. Business rules live in `backend/services/` (workflows, one sub-package per capability; steps 2–5 build `services/statement_analysis/`, and step 4 also `services/documents/`) and `backend/domain/` (pure logic), not in views or serializers.
- Every tenant-owned query is scoped by workspace membership in one place: an application-layer helper plus queryset scoping. Never ad hoc in views.
- Another workspace's objects return `404`, never `403`, so their existence is not revealed.
- Fixtures use fictional data only. API tests cover the error envelope, permissions by role, and pagination.
- Calculation or validation output changes follow the engine version policy ([conventions §10](../data/FINANCIAL_CALCULATION_CONVENTIONS.md#10-reproducibility-and-versioning)).
- Update DATA_MODEL, API_CONVENTIONS and the CHANGELOG in the same pull request.

## Step 0 — Prerequisites

| Task | Detail | Done when | Status (2026-10-27) |
|---|---|---|---|
| Python move (A1, recommended) | Install Python 3.13; recreate `.venv`; set `requires-python >=3.12`, ruff `py312`, mypy `3.12`; re-lock with `--python-version 3.12`; CI matrix `3.12` and `3.13` | All gates green; dev `pip-audit` clean | Done locally; CI on the branch pending |
| PostgreSQL available (A11) | `docker compose up -d db` (port 55432 by default), or a dedicated role and database you own. Development settings now require PostgreSQL | `pytest` passes with `FINLUME_TEST_DB_ENGINE=postgresql`, recorded in the PR | Done in CI (PostgreSQL 17) |
| CI running (A10) | Push a branch; enable branch protection, private vulnerability reporting and Dependabot | All CI jobs green | CI green; Dependabot configured; repository settings pending |
| Step 1 decisions | A3 (401/403), A5 (login identifier), A6 (session policy), A7 (app name), A9 (login protection), A8 (audit retention) | Recorded in PRODUCT_SCOPE §10 or an ADR | Done: [ADR-0007](../decisions/ADR-0007-authentication-and-sessions.md) and [ARCHITECTURE_DECISIONS](../architecture/ARCHITECTURE_DECISIONS.md#smaller-conventions-decided-2026-10-27) |

## Step 1 — Workspace ownership and authorisation

**Goal:** users sign in, belong to organizations, and act only inside workspaces they are members of (FR-001–FR-006, NFR-010).

Step 1 is specified in the **[tenancy implementation plan](TENANCY_IMPLEMENTATION_PLAN.md)**, following [ADR-0008](../decisions/ADR-0008-organizations-and-workspace-tenancy.md) and [ADR-0007](../decisions/ADR-0007-authentication-and-sessions.md). It is delivered as PRs 1a–1d:

- **1a:** the tenancy models (`organizations` and `workspaces` apps), the personal-workspace data migration, and the access resolver.
- **1b:** authentication, registration and the `audit` app.
- **1c:** the workspace API, including ownership recovery.
- **1d:** the organization API and membership synchronisation.

Its acceptance criteria and query budgets are in that plan, §4 and §8.

## Step 2 — Financial statement and normalised fact models

**Goal:** the persistence model for statements and facts, with provenance (FR-010, FR-012, FR-016, FR-017).

Delivered as two PRs:

- **2a** (*implemented 2026-10-27*): both apps, the five models, migrations, constraints, the read-only admin and their tests.
- **2b:** the mapping layer and the assembly rule.

- **Apps:** `financial_records` (`ReportingEntity`, `FinancialStatement`, `StatementLineItem`, `FinancialFact`) and `documents` (`SourceDocument`; only `manual_entry` in this step).
- **Constraints, per DATA_MODEL:**
  - `RESTRICT` provenance keys (FA-05);
  - partial unique indexes for "one current version": at most one validated and one draft version per statement and period, so a restatement can be drafted while the validated version stays in use (decided 2026-10-27);
  - composite foreign keys (PostgreSQL) so related rows cannot cross workspaces and facts match their statement;
  - `CHECK (version = 1) = (supersedes IS NULL)`;
  - a currency format CHECK;
  - `UNIQUE(statement, line_item)` on facts.
- **Mapping layer:** in `services/statement_analysis/`, turn persisted facts into `FinancialFactSet` and back. The domain never sees ORM objects.
- **Assembly rule (A2):** one analysis input = the latest validated, non-superseded statement of each type for (`entity`, `period_start`, `period_end`, `period_type`), all in one currency.
- **Acceptance:**
  - Migration tests on **PostgreSQL**.
  - Constraint tests: duplicate current version rejected, mixed-currency assembly rejected, a balance sheet combines with the income statement for the same period.
  - Restrict tests: a statement referenced by a run cannot be deleted; a workspace cascade succeeds.

## Step 3 — Manual statement entry and validation

**Goal:** enter all three statements by hand, see validation warnings, and confirm (FR-011, FR-015, FR-020–FR-023).

- **Endpoints:**
  All under `/workspaces/{ws}/` ([API conventions](../api/API_CONVENTIONS.md#resources-and-urls)):
  - `GET/POST entities/`
  - `GET/POST entities/{id}/statements/` (draft with line items)
  - `PATCH statements/{id}/` while in draft
  - `POST statements/{id}/validate/`: draft → validated; creates facts
  - `POST statements/{id}/restatements/`: new version plus reason
- **Input validation:**
  - Decimal strings only (floats rejected).
  - At most 6 decimal places, and magnitude below 10²⁴ after normalisation (FA-15).
  - Valid ISO currency format and scale enum.
  - A line-item code allowed only within its own statement type.
  - Sign issues are reported, not flipped.
- **Line-item definitions** (A4) shown as help text; the API exposes the taxonomy with definitions.
- **Acceptance:** acceptance criteria 3, 5 and 8. Restating creates version 2 and leaves version 1's facts intact. Validation issues are returned without blocking validation.

## Step 4 — CSV import with row-level errors and provenance

**Goal:** upload a CSV, review the mapping and per-row errors, confirm (FR-013, FR-014, FR-016).

- **Upload endpoint:**
  - `MultiPartParser` on this view only.
  - A new `FINLUME_MAX_UPLOAD_BYTES`, checked **before** storing (FA-06).
  - A row cap.
  - `FILE_UPLOAD_TEMP_DIR` set to a private directory.
  - Content sniffing (UTF-8 text, CSV); SHA-256; random storage key in `private_documents`.
  - A duplicate-file warning.
- **Parsing:** the workflow is in `services/statement_analysis/`, and file intake in `services/documents/`. Pure parsing rules go in `domain/`. There is no `ingestion` app unless import batches need tables:
  - A strict, documented column schema (label, amount, optional code).
  - Explicit decimal format; parentheses for negatives recorded in `raw_value`.
  - Never a float intermediate.
  - Errors reported per row and column, in the envelope `details`.
- **Mapping review:** a proposed code per row (exact label match first; no fuzzy guessing in the MVP); the user confirms; confirmation creates the draft statement, then follows the step 3 flow.
- **Admin:** a read-only `SourceDocument` admin with no file URL widget (FA-21).
- **Acceptance:**
  - Acceptance criterion 4.
  - An oversized file is rejected without anything being stored.
  - A malformed row yields a row-level error and the rest of the import is not partially saved.
  - Every fact traces to row, statement version and document (criterion 9).
  - `Idempotency-Key` honoured on upload.

## Step 5 — Deterministic analysis and persisted results

**Goal:** run, save and reload immutable analyses (FR-030–FR-034, FR-040, NFR-005).

- **Domain:** `fingerprint(facts)` as a pure function in the canonical format (FA-11).
- **App:** `analysis` (`AnalysisRun`, `MetricResult`, `AnalysisIssue`, plus the input-fact join, `RESTRICT`).
- **Workflow** (`services/statement_analysis/`):
  1. Assemble the inputs (A2).
  2. Call `run_statement_analysis`.
  3. Persist the run, results (`numeric(24,6)`; values below `MAX_RESULT_ABS` by construction), issues, inputs as decimal strings, `engine_version` and fingerprint in one transaction.
  4. Write an `analysis.run` audit event.
- **App:** `reports` (`Report` with title, notes and ordered runs).
- **Endpoints**, all under `/workspaces/{ws}/`: `POST entities/{id}/analyses/` (body: period), `GET analyses/{id}/`, `GET entities/{id}/analyses/`, and `GET/POST/PATCH reports/`.
- **Acceptance:**
  - Acceptance criteria 6 and 7.
  - Re-running unchanged inputs gives an identical fingerprint and values.
  - Runs are immutable (no update endpoint; a model guard).
  - An out-of-range result is persisted as not computable with `result_out_of_range`.
  - Decimal round-trip exactness verified on **PostgreSQL**.

## Step 6 — API tests and OpenAPI schema

**Goal:** a stable, documented v1 contract for the web client and, later, mobile (FR-050, FR-052).

- Add `drf-spectacular` (a new dependency; record it in ADR-0004's dependency list), with the schema at `/api/v1/schema/`. In production, serve it only to authenticated users or not at all (decide in the PR).
- Add a schema snapshot test that fails when the schema changes unintentionally. Enforce the coverage floor (`fail_under = 85`, FA-23).
- API tests are written in every step. This step closes the gaps: an end-to-end API test of the whole workflow, cross-workspace isolation for every endpoint, and the pagination and ordering rules.
- **Acceptance:**
  - The schema validates.
  - The TypeScript client generates from it without manual edits.
  - The end-to-end test covers acceptance criteria 1–10 at the API level.

## Step 7 — React web dashboard with interactive charts

**Goal:** the MVP user interface (FR-040–FR-043, NFR-030, NFR-031), following ADR-0006.

- Build on the existing `apps/web` shell, which already has Vite, React, TypeScript (strict), TanStack Query, React Hook Form with Zod, Tailwind with shadcn/ui conventions, Apache ECharts and the `/api` dev proxy ([Frontend applications](FRONTEND.md)). Replace the hand-written API client with one generated from the step 6 schema. Swap empty states for real data screens as each API lands, and keep the synthetic sample clearly separated.
- **Screens:** sign-in and workspaces; entities; statement entry and CSV import with mapping review; analysis view (metrics with methodology, inputs and issues; validation issues shown next to the metrics they affect, FA-18); saved reports.
- **Charts:** stored values only; missing values shown as gaps, never interpolated (FR-043); a table alternative for every chart (NFR-030); currency and scale always shown (NFR-031).
- **Front-end CI:** a new job running typecheck, lint, Vitest, Playwright smoke tests and an axe accessibility check.
- **Acceptance:** acceptance criteria 1–9 and 13 demonstrated in the browser.

## Step 8 — PostgreSQL integration testing and production hardening

**Goal:** deployable, self-hostable MVP (NFR-040–NFR-061, acceptance criteria 11 and 12).

- **PostgreSQL:** PostgreSQL-only tests marked `@pytest.mark.postgres` (numeric precision at the column limits, partial indexes, concurrent version creation). PostgreSQL has been the CI database since step 0, so this step completes the coverage rather than introducing it.
- **Shared throttle cache:** `DatabaseCache` (FA-09).
- **Login protection** reviewed (FA-08).
- **Log scrubbing**, and mapping known integrity errors to `409` (FA-24).
- **Deployment:**
  - add Gunicorn;
  - a production `compose` example (reverse proxy with TLS, app, PostgreSQL, private volume);
  - reverse-proxy body limit;
  - `SECURE_REDIRECT_EXEMPT` or health probes over TLS, and the HSTS rollout (FA-17);
  - backup and restore guide.
- **Workspace, organization and user export and deletion** (FR-054, FR-055), with the grace period per A8. These are the lifecycle workflows ADR-0008 §7 requires before the admin may delete tenancy data. Files are deleted after the transaction commits, with a cleanup command.
- **Acceptance:** acceptance criteria 11 and 12. `check --deploy` is clean apart from documented HSTS staging. A restore drill is documented.

## Exact next task

**Accept ADR-0008 (PR 0), then PR 1a of the [tenancy plan](TENANCY_IMPLEMENTATION_PLAN.md#8-implementation-sequence):
the `organizations` and `workspaces` models, the personal-workspace data migration and the
access resolver.** It is test-first and verified on PostgreSQL.

Step 0's work is done: the Python move (A1), PostgreSQL in CI (A11) and the step 1
decisions (ADR-0007, A7, A8). It is complete once its pull request is green and merged.
