# Foundation Audit and Pre-MVP Readiness Review

| | |
|---|---|
| Date | 2026-10-25 |
| Scope | Everything in the working tree at the end of Phase 0: backend code, settings, tests, dependency manifests, CI, scripts and all documentation |
| Repository state | Branch `main`, last commit `c9e7e6a`. The Phase 0 foundation is **uncommitted** (modified `README.md` plus new files). `LICENSE` is unchanged. |
| Environment | Windows 11, Windows PowerShell 5.1, Python 3.10.7 (the only interpreter installed), Node 22. Docker CLI present, daemon not running. Two pre-existing PostgreSQL services (16 and 17) listen on ports 5432 and 5433. |
| Method | Read the code and docs, re-ran every gate from clean caches, probed the engine with extreme inputs, and read Django's source where behaviour was in doubt |

**Verdict: ready to start the MVP**, on the conditions in [§9](#9-readiness-verdict). No
Critical findings. Four High findings: one was fixed during this audit, and three need either
a decision from the maintainer or an environment action before the steps they block.

## 1. Check results

Everything below ran on 2026-10-25 on the machine described above, unless marked otherwise.

| Check | Command | Result |
|---|---|---|
| Formatting | `ruff format --check .` | **Passed**: 63 files |
| Lint (includes bandit-derived `S` rules) | `ruff check .` | **Passed** |
| Static types (strict, django-stubs) | `mypy .` | **Passed**: 62 source files |
| Django system checks | `manage.py check --fail-level WARNING --settings=config.settings.test` | **Passed**: 0 issues |
| Migration drift | `manage.py makemigrations --check --dry-run` | **Passed**: no changes |
| Unit and API tests (SQLite, in-memory) | `pytest --cov` | **Passed**: 110 passed, 0 failed, 0 skipped; 91 % branch coverage |
| Deployment checks (production settings, placeholder env, unreachable DB port) | `manage.py check --deploy` | **1 warning**: `security.W004` (HSTS), by design, see FA-17 |
| Runtime dependency audit | `pip_audit -r requirements/base.txt` | **Passed**: no known vulnerabilities |
| Dev dependency audit on Python 3.10 | `pip_audit -r requirements/dev.txt` | **Failed**: 6 advisories in `filelock` 4.1.0 (FA-04) |
| Lock consistency | Recompile both locks over copies of themselves and compare | **Passed**: 0 differing lines |
| Installed environment vs lock | `pip check` plus comparison with `requirements/dev.txt` | **Passed** |
| Python 3.12 / 3.13 resolution | `uv pip compile --python-version 3.12` and `3.13` | **Passed**: same top-level versions; `filelock` 4.2.4 |
| Local gate scripts | `scripts/check.ps1`, `scripts/check.sh` (Git Bash) | **Passed**: both exit 0 on the final tree (110 tests) |
| Docs links and anchors; Mermaid rendering | Relative-link and anchor checker; `@mermaid-js/mermaid-cli` 11.4.2 | **Passed**: 36 Markdown files with no broken links; 7/7 diagrams render on the final tree |
| **PostgreSQL tests** | `pytest` with `FINLUME_DB_ENGINE=postgresql` | **Not executed**: no PostgreSQL that Finlume owns was available (FA-03) |
| **GitHub Actions CI** | `.github/workflows/ci.yml` | **Not executed**: nothing has been pushed (FA-12) |
| Tests on Python 3.11–3.13 | — | **Not executed**: only 3.10 is installed |

## 2. Findings summary

| ID | Severity | Area | Finding | Status |
|---|---|---|---|---|
| FA-01 | High | Engine | Ratio computation raised on very large quotients | **Fixed** |
| FA-02 | High | Data model | No rule for assembling one fact set from separate statements | **Needs approval** |
| FA-03 | High | PostgreSQL | No test has ever run on PostgreSQL | **Resolved** in CI ([§11](#11-follow-up-2026-10-27)) |
| FA-04 | High | Python | Python 3.10 reaches end of life this month | **Fixed** ([§11](#11-follow-up-2026-10-27)) |
| FA-05 | Medium | Data model | Planned `PROTECT` keys would block workspace and user deletion | **Fixed** (design docs) |
| FA-06 | Medium | Security | Docs claimed an upload size limit that Django does not enforce for files | **Fixed** (docs and comment); enforcement planned |
| FA-07 | Medium | API | 401 vs 403 for unauthenticated requests is inconsistent across docs | **Decided**: 401 ([ADR-0007](../decisions/ADR-0007-authentication-and-sessions.md)); implement in step 1 |
| FA-08 | Medium | Security | No brute-force protection on admin or (future) API login | **Decided** ([ADR-0007](../decisions/ADR-0007-authentication-and-sessions.md)); implement in step 1 |
| FA-09 | Medium | Security / ops | Throttle counters are per process | Open: plan step 8 |
| FA-10 | Medium | Engine | Line-item definitions behind four ratios are ambiguous | **Needs approval** |
| FA-11 | Medium | Engine | Input fingerprint is designed but not implemented | Open: plan step 5 |
| FA-12 | Medium | CI | Workflow never executed; Python 3.13 path unverified | **Mostly resolved**: CI green, Dependabot added; SHA pinning and repository settings open ([§11](#11-follow-up-2026-10-27)) |
| FA-13 | Medium | Dev environment | Local PostgreSQL port collision; risk of testing against an unrelated server | **Fixed** (docs and `.env.example`) |
| FA-14 | Medium | Observability | 4xx log lines lost their request ID | **Fixed** |
| FA-15 | Medium | Engine / ingestion | No magnitude or precision bounds on facts before persistence | Open: plan step 3 |
| FA-16 – FA-27 | Low | Various | See [§5](#5-low-findings) | Mixed |

## 3. High findings

### FA-01 — Ratio computation raised on very large quotients (Fixed)

- **Evidence:** `domain/calculations/metrics.py` `compute_ratio` quantised every quotient with `CALCULATION_CONTEXT` (`prec=34`, traps `InvalidOperation` and `Overflow`). The inputs `total_current_assets = 999999999999999999999999.999999` and `total_current_liabilities = 0.000001` both fit the planned `numeric(30,6)` column, yet they raised `decimal.InvalidOperation` (reproduced). The result `1E+20 / 1` was returned, but it would not fit the planned `numeric(24,6)` result column. The domain also accepts exponents large enough to trap `Overflow`.
- **Impact:** a single odd input, such as a mis-scaled figure, would crash an analysis request with a 500 instead of reporting a problem.
- **Fix applied:** `precision.MAX_RESULT_ABS = Decimal("1E+18")`. `compute_ratio` catches `Overflow`, checks the magnitude before quantising and again after (rounding can carry `999…999.9999995` up to the bound), and returns `value=None` with the new `IssueCode.RESULT_OUT_OF_RANGE`. The conventions doc and changelog are updated. `ENGINE_VERSION` stays `0.1.0`, because it has never been released and no result has ever been persisted (policy clarified in [the conventions, §10](../data/FINANCIAL_CALCULATION_CONVENTIONS.md#10-reproducibility-and-versioning)).
- **Acceptance (met):** `test_out_of_range_results_are_reported_not_raised` (5 cases, including the rounding-up and context-overflow cases) and `test_largest_storable_result_is_kept` pass.

### FA-02 — No rule for assembling one fact set from separate statements (Needs approval)

- **Evidence:** [DATA_MODEL §4.6](../data/DATA_MODEL.md#46-financialstatement-mvp) stores one `FinancialStatement` per statement type, each with its own `period_start`, `period_end` and `currency`. §6 says "an analysis combines facts with identical period bounds only". Nothing says what `period_start` a balance sheet carries, because a balance sheet is a position at a date. The engine's `FinancialFactSet` takes exactly one `ReportingPeriod` and one `Currency` (`domain/financial_statements/facts.py`).
- **Impact:** if a balance sheet were stored with `period_start = period_end`, it would never combine with the income statement. Return on equity, return on assets and every other cross-statement ratio would then always be "missing input", and FR-030 could not be met for persisted analyses.
- **Recommended default:**
  1. A balance sheet is recorded against the **reporting period it closes**: the same start, end and type as the income statement, with figures as of `period_end`. This matches `ReportingPeriod.as_of`.
  2. An analysis input is the latest non-superseded, validated statement of **each** type for one (`entity`, `period_start`, `period_end`, `period_type`).
  3. All of those statements must share one currency. Otherwise the analysis is rejected at the input boundary with an error-severity issue, because there is no FX conversion (D-03).
  4. A line-item code may only be mapped within a statement of its own `LineItem.statement_type`.
- **Acceptance:** documented in DATA_MODEL §6 and the calculation conventions. The step 5 tests cover combining all three statements, a currency mismatch and a missing statement type.

### FA-03 — No test has ever run on PostgreSQL (Open: environment)

- **Evidence:** the Docker daemon is not running. The only reachable PostgreSQL servers are pre-existing Windows services `postgresql-x64-16` and `postgresql-x64-17` on ports 5432 and 5433. They are listening on all interfaces, and Finlume does not own them. pytest-django **creates and drops** `test_<POSTGRES_DB>`, so running the suite there was not attempted. CI is configured for PostgreSQL 17 (`.github/workflows/ci.yml`, job `backend`), but has never run.
- **Impact:** the MVP depends on PostgreSQL-specific behaviour that SQLite does not reproduce: exact `numeric(30,6)` storage, partial unique indexes, CHECK constraints and transactional DDL. Phase 0 has no models that exercise these, so the risk starts with plan step 1.
- **Recommendation:** before step 1 merges, either start Docker Desktop and run `docker compose up -d db` with a free `POSTGRES_PORT` (FA-13), or push a branch so CI runs on PostgreSQL. **Plan change:** PostgreSQL verification becomes a prerequisite of steps 1–5, not only part of step 8 (see the [MVP plan](../development/MVP_IMPLEMENTATION_PLAN.md)).
- **Acceptance:** one documented, green `pytest` run with `FINLUME_DB_ENGINE=postgresql`, locally against the compose container or in CI.

### FA-04 — Python 3.10 reaches end of life (Needs approval, D-01)

- **Evidence:** the only installed interpreter is 3.10.7. `pyproject.toml` has `requires-python = ">=3.10"`. CPython 3.10 reaches end of life in October 2026, after which it gets no security fixes. On 3.10 the dev lock pins `filelock` 4.1.0 (via `pip-audit`, then `cachecontrol`), which has six advisories whose fix (4.2.1) needs Python ≥ 3.11. The runtime dependencies are not affected.
- **Migration assessment:** low risk.
  - Django 5.2.18, DRF 3.18.3 and psycopg 3.3.6 declare support for Python 3.10 through 3.14.
  - `psycopg-binary` 3.3.6 has cp312 and cp313 wheels for Windows (`win_amd64`) and Linux (`manylinux x86_64`).
  - Universal resolution for 3.12 and 3.13 succeeds with the same top-level versions.
  - The code uses no 3.10-only constructs.
- **Recommended steps (after approval):**
  1. Install Python 3.13, or 3.12.
  2. Recreate `.venv`.
  3. Set `requires-python = ">=3.12"`, ruff `target-version = "py312"` and mypy `python_version = "3.12"`.
  4. Re-lock with `--python-version 3.12`, which drops the `< 3.11` markers.
  5. Set the CI matrix to `["3.12", "3.13"]`.
  6. Run all gates. Staying on Django 5.2 LTS is fine; Django 6.x is a separate, later decision.
- **Acceptance:** all gates pass on the new interpreter, and the dev `pip-audit` is clean.

## 4. Medium findings

### FA-05 — Planned `PROTECT` keys would block workspace and user deletion (Fixed in design docs)

- **Evidence:** DATA_MODEL and DATABASE_CONVENTIONS specified `PROTECT` on every provenance key (statement → entity, fact → statement, run → input facts, report → run, statement → superseded version), while workspace children `CASCADE`. In Django, `PROTECT` raises even when the referencing rows are deleted in the same cascade (`django/db/models/deletion.py`, `PROTECT` versus `RESTRICT` and `add_restricted_objects`). Deleting a user would cascade into their personal workspace and raise `ProtectedError`. Deleting two statement versions together would also fail.
- **Fix applied:** the design now uses `RESTRICT` (DATA_MODEL principle 4 and the entity tables, DATABASE_CONVENTIONS, DATA_LIFECYCLE). This keeps "cannot delete evidence that something else still references" and allows a full workspace cascade.
- **Acceptance (plan steps 1–2):** tests show that (a) deleting a workspace with statements, facts and runs succeeds, (b) deleting a statement version referenced by a run fails with `RestrictedError` (API: `409`), and (c) deleting a user deletes their personal workspace.

### FA-06 — No upload size limit for files (docs and comment fixed; enforcement planned)

- **Evidence:** `config/settings/base.py` sets `DATA_UPLOAD_MAX_MEMORY_SIZE` and `FILE_UPLOAD_MAX_MEMORY_SIZE` from `FINLUME_MAX_REQUEST_BYTES`. Django applies the first only to the request body and to non-file multipart fields (`django/http/multipartparser.py`, the field branch). The second is just the threshold for spooling an upload to a temporary file. THREAT_MODEL T7, SECURITY_AND_PRIVACY, DATA_FLOW and LOCAL_SETUP claimed a file size limit. There is no upload endpoint and DRF accepts JSON only (`DEFAULT_PARSER_CLASSES`), so there is no live exposure.
- **Fix applied:** corrected the settings comment and the four documents.
- **Acceptance (plan step 4):**
  - The CSV endpoint enables `MultiPartParser` only on that view.
  - It rejects files above `FINLUME_MAX_UPLOAD_BYTES` (a new setting) with `413` or `400` **before** storing them, and caps the row count.
  - The deployment guide sets a reverse-proxy body limit.
  - `FILE_UPLOAD_TEMP_DIR` points to a private directory.

### FA-07 — 401 vs 403 for unauthenticated requests (Needs approval)

- **Evidence:** with only `SessionAuthentication`, DRF answers unauthenticated requests with **403** (`not_authenticated`), because that class sends no `WWW-Authenticate` challenge. `tests/api/test_security_defaults.py::test_anonymous_requests_are_rejected_by_default` now pins this, and API_CONVENTIONS documents it. [PRODUCT_SCOPE acceptance criterion 10](../product/PRODUCT_SCOPE.md#11-mvp-acceptance-criteria) expects **401**.
- **Options:**
  - (a) Keep 403 and correct criterion 10. Clients branch on `error.code`.
  - (b) Return 401 with a `SessionAuthentication` subclass whose `authenticate_header()` returns a session challenge. This is more conventional for SPAs and the future mobile client.
- **Recommendation:** (b), decided before step 1 builds the login endpoints.

### FA-08 — No brute-force protection on login (Open: plan step 1)

- **Evidence:** DRF throttles do not cover the Django admin login (`config/urls.py`, `admin.site.urls` at `FINLUME_ADMIN_URL_PATH`). No API login exists yet.
- **Recommendation:** in step 1, give the API login view a dedicated scoped throttle (for example `login: 5/minute` per IP and username), and record `auth.login_failed` audit events. For the admin, either put it behind the same protection or keep it off public hosts. A lockout library would be a new dependency and needs approval.
- **Acceptance:** a test shows the sixth failed login within a minute returns `429`.

### FA-09 — Throttle counters are per process (Open: plan step 8)

- **Evidence:** there is no `CACHES` setting, so DRF throttles use Django's default per-process `LocMemCache`. With N Gunicorn workers the effective limit is N times the configured rate (NFR-015).
- **Recommendation:** use the `DatabaseCache` backend (no Redis needed; `createcachetable` at deploy), or Redis once Phase 2 introduces it.
- **Acceptance:** a multi-process deployment test, or documented operator configuration.

### FA-10 — Ambiguous line-item definitions behind four ratios (Needs approval)

- **Evidence:** `domain/financial_statements/line_items.py` defines codes without definitions. These affect results:
  - `total_debt` (`debt_to_equity`): does it include lease liabilities, the current portion of long-term debt, or bank overdrafts?
  - `total_equity` (`debt_to_equity`, `return_on_equity`, balance sheet identity): does it include non-controlling interests?
  - `net_income` (`net_margin`, `return_on_equity`, `return_on_assets`): attributable to owners of the parent, or including non-controlling interests? (This matters with the `total_equity` choice: ROE should pair like with like.)
  - `operating_income` (`operating_margin`): reported operating profit, or EBIT?

  The formulas themselves are unambiguous and must not change. The meaning of their inputs is undefined.
- **Recommendation:** approve a short definitions table in FINANCIAL_CALCULATION_CONVENTIONS §4, shown as help text in the entry UI. Suggested defaults: `total_debt` = interest-bearing borrowings, current plus non-current, excluding lease liabilities; `total_equity` = total equity **including** non-controlling interests (so the balance sheet identity holds); `net_income` = profit for the period **including** non-controlling interests (consistent with that equity); `operating_income` = operating profit as reported. Exclusions can become new codes later.
- **Acceptance:** definitions documented before step 3's entry form ships.

### FA-11 — Input fingerprint designed but not implemented (Open: plan step 5)

- **Evidence:** [the calculation conventions, §10](../data/FINANCIAL_CALCULATION_CONVENTIONS.md#10-reproducibility-and-versioning) specify the canonical JSON format. `AnalysisOutcome` (`domain/calculations/analysis.py`) carries the engine version, period, currency, issues and per-metric inputs, but no fingerprint.
- **Recommendation:** implement `fingerprint(facts: FinancialFactSet) -> str` in the domain, as a pure function. Format every value as a fixed-point string with exactly 6 decimal places, and reject values with more than 6 decimal places rather than rounding them (otherwise `1.0` and `1.000000` stay equal, but precision could be lost silently).
- **Acceptance:** golden-value test, order independence, and equal fingerprints for `Decimal("1.0")` and `Decimal("1.000000")`.

### FA-12 — CI never executed; Python 3.13 path unverified (Open)

- **Evidence:** `.github/workflows/ci.yml` is new and has never run. The 3.13 leg uses different transitive versions (for example `django-stubs-ext` 6.1.2 and `asgiref` 3.13.0), and pytest runs with `filterwarnings = ["error"]`, so a new deprecation warning on 3.13 would fail tests. Third-party actions are pinned by tag, not commit SHA, and there is no Dependabot configuration.
- **Recommendation:** push a branch (needs your authorisation) and fix whatever the first run surfaces. Add `.github/dependabot.yml` for `pip` (in `backend/`) and `github-actions`. Consider SHA-pinning actions.
- **Acceptance:** all three CI jobs are green on a pull request.

### FA-13 — Local PostgreSQL port collision (Fixed in docs and `.env.example`)

- **Evidence:** `compose.yaml` maps `127.0.0.1:${POSTGRES_PORT:-5432}`. On this machine 5432 and 5433 are taken by unrelated PostgreSQL services. Without Docker, Postgres-mode Django would connect to them, and pytest would create and drop `test_finlume` on them.
- **Fix applied:** a LOCAL_SETUP warning and a `.env.example` comment. One variable (`POSTGRES_PORT`, for example `55432`) moves both the container and Django.
- **Note for the machine owner:** those two services listen on `0.0.0.0` and `::`, which is outside Finlume's scope but worth checking.

### FA-14 — 4xx log lines lost their request ID (Fixed)

- **Evidence:** `RequestIDMiddleware` reset the context variable on exit, but Django logs 4xx responses (`django.request`, `log_response`) after the middleware chain returns. The captured log showed `request_id=-` for a 404.
- **Fix applied:** the middleware also stores the ID in `request.META["FINLUME_REQUEST_ID"]`, and `RequestIDFilter` prefers the request attached to the record.
- **Acceptance (met):** `tests/api/test_health.py::test_client_error_log_lines_keep_the_request_id`.

### FA-15 — No magnitude or precision bounds on facts before persistence (Open: plan step 3)

- **Evidence:** `FinancialFactSet` and `normalize_amount` accept any finite `Decimal` (exact scaling, `domain/financial_statements/units.py`). The planned columns are `numeric(30,6)`. A reported `1.2345678` crores normalises exactly, but `reported_amount` with 7 decimal places would be rounded by the database. An amount ≥ 10²⁴ fails on insert and becomes a 500.
- **Recommendation:** input validation (serializer or application layer) rejects amounts with more than 6 decimal places in `reported_amount`, and normalised values whose magnitude is ≥ 10²⁴, with field-level `validation_error`s.
- **Acceptance:** API tests for both cases return `400` with the offending row and field.

## 5. Low findings

| ID | Finding and evidence | Recommendation | Status |
|---|---|---|---|
| FA-16 | A result smaller than 0.0000005 is stored as `0.000000` (`quantize_result`), indistinguishable from a true zero | Accept; document that 6 dp is the resolution, and reconsider per metric if needed | Accepted |
| FA-17 | `SECURE_SSL_REDIRECT=True` (production) answers plain-HTTP health probes with `301`. `check --deploy` W004 because HSTS defaults to 0 | Probe through the TLS proxy, or add `SECURE_REDIRECT_EXEMPT = [r"^api/v1/health/$"]` at deployment; enable HSTS once HTTPS is verified | Deployment decision |
| FA-18 | A metric computed from sign-violating input (for example negative revenue) has no metric-level issue; only `validation_issues` carries `unexpected_sign` | Dashboard shows validation issues next to affected metrics (step 7) | Planned |
| FA-19 | Session lifetime is Django's default of 2 weeks, with no idle timeout | Decide a policy, for example 8 hours with `SESSION_SAVE_EVERY_REQUEST` | Needs approval |
| FA-20 | `User.email` has no database-level non-blank check, and login uses `username` | Decide whether to sign in by email. If yes, add a `CHECK (email <> '')` and an email-based backend in step 1 | Needs approval |
| FA-21 | `PrivateFileSystemStorage.url()` raises by design, so Django admin's default `FileField` widget would crash on documents | Custom read-only admin widget when `SourceDocument` lands (step 4) | Planned |
| FA-22 | Test settings pointed management commands at the development SQLite file | `config/settings/test.py` now uses `var/test.sqlite3`; pytest still uses an in-memory database | **Fixed** |
| FA-23 | No coverage threshold (`--cov-fail-under`) in CI or the scripts | Add `fail_under = 85` to `[tool.coverage.report]` once CI is green | Planned |
| FA-24 | Unhandled database errors are logged with their messages, which can contain user data (for example an `IntegrityError` showing an email) | Log scrubbing policy, and map known integrity errors to `409` in the application layer (step 8) | Planned |
| FA-25 | `load_env_file` also runs under production settings (it never overrides real environment variables) | Accept; documented in LOCAL_SETUP | Accepted |
| FA-26 | The planned app `organizations` would hold `Workspace` and `Membership` | Name it `workspaces`, keeping `organizations` for the future `Organization` grouping | Needs approval (naming) |
| FA-27 | The `missing_input` message read "needs a, b, which is not provided" | Now "needs a and b, which are not provided" | **Fixed** |

## 6. Conformance: documented architecture vs implementation

| Documented | Implemented | Verdict |
|---|---|---|
| Modular monolith; `domain/` free of Django, DRF and outer layers | `tests/test_architecture.py` scans every `domain/*.py` import (14 cases) | Conforms |
| Versioned API `/api/v1/` | `config/urls.py` `re_path(r"^api/(?P<version>v1)/")`, `URLPathVersioning`, `ALLOWED_VERSIONS=["v1"]`; `/api/v2/` returns a JSON 404 (tested) | Conforms |
| Secure by default: authentication required | `DEFAULT_PERMISSION_CLASSES = [IsAuthenticated]`; health opts out explicitly; anonymous → 403 (tested this audit) | Conforms (status code: FA-07) |
| CSRF on session writes; no CORS | `SessionAuthentication` enforces CSRF (tested this audit); no CORS middleware or dependency; `CSRF_TRUSTED_ORIGINS` from the environment | Conforms |
| Host validation | Production requires non-empty `DJANGO_ALLOWED_HOSTS`; development defaults to localhost; tested | Conforms |
| Secrets from the environment only | Production requires a 50+ character key; development and test generate a random per-process key; no secret in the repository (pattern scan clean) | Conforms |
| Safe error envelope | `apps/core/exceptions.py`; 404 and 500 handlers; parse errors sanitised; unexpected errors propagate, roll back and return a JSON 500 | Conforms |
| Health endpoint reveals nothing | Returns only `status` and `checks.database`; `no-store`; outside `ATOMIC_REQUESTS`; DB error text only in logs (tested) | Conforms |
| Private documents never get public URLs | `PrivateFileSystemStorage.url()` raises; `default` and `private_documents` are both private; `finlume.E001` system check (tested) | Conforms |
| Custom user model before the first migration | `AUTH_USER_MODEL="accounts.User"`; `accounts.0001_initial` depends on `auth.0012`; `public_id` UUID; case-insensitive unique email (tested) | Conforms |
| Production hardening | `DEBUG=False`, secure cookies, SSL redirect, JSON-only renderer, PostgreSQL required (tested this audit) | Conforms |
| Decimal-only, deterministic, versioned engine | Floats rejected; explicit context; half-even 6 dp; `ENGINE_VERSION`; determinism tested | Conforms (after FA-01) |
| Upload size limits | Not enforced for files | Docs corrected (FA-06) |
| PostgreSQL-tested persistence | Never executed | Gap (FA-03) |
| Hashed, reproducible dependencies | `pyproject.toml` declares; `uv` universal hashed locks; `--require-hashes` installs; no drift | Conforms |
| Planned folders not created prematurely | No `application/`, `providers/`, `jobs/` or frontend apps; documented triggers | Conforms at audit time. The client shells were added afterwards at the maintainer's request (see [ADR-0006](../decisions/ADR-0006-client-stack.md#implementation-notes-2026-10-25)) |

## 7. Data model readiness

Only `accounts.User` exists. The MVP needs the following, in this order. Everything else in
[DATA_MODEL](../data/DATA_MODEL.md) waits, including Organization and all Phase 2–5 entities.

| Need | Minimum schema | Blocked by |
|---|---|---|
| Workspace ownership | `Workspace` (kind, `personal_owner`), personal workspace created with the user | FA-26 naming (non-blocking) |
| Memberships and permissions | `Membership(workspace, user, role)`; owner, editor, viewer policy in `application/` | FA-07 |
| Statements | `ReportingEntity`, `FinancialStatement` (versioned, `supersedes`, partial unique "one current version") | FA-02, FA-03 |
| Raw input and provenance | `SourceDocument` (`manual_entry` first, then `csv_upload`), `StatementLineItem` | FA-06 (CSV only) |
| Normalised facts | `FinancialFact` with `derived_from` (`RESTRICT`) and `review_status` | FA-10, FA-15 |
| Saved analysis and result versioning | `AnalysisRun` (engine version, fingerprint, input-fact join), `MetricResult`, `AnalysisIssue` | FA-02, FA-11 |
| Audit | `AuditEvent` (no financial values) | Retention (D-07) |
| Reports | `Report` (title, notes, runs) | — |

Unresolved decisions on ownership, deletion, retention and audit are D-07 (retention periods,
including the 30-day grace period and 1-year audit retention), FA-07, FA-19, FA-20 and FA-26.
There is also an open question with no recommendation yet: whether a business workspace may
outlive every owner (proposed: no; the last owner must transfer ownership or delete).

## 8. Decisions requiring maintainer approval

| # | Decision | Recommendation | Needed before |
|---|---|---|---|
| A1 (FA-04, D-01) | Raise the Python floor to 3.12 and move the local and CI interpreters | Approve; install Python 3.13 and recreate `.venv` | Step 1 (recommended) |
| A2 (FA-02) | Rule for assembling statements into one analysis input | Approve the recommended default in FA-02 | Step 2 |
| A3 (FA-07) | 401 or 403 for unauthenticated API calls | 401 via a session challenge header | Step 1 |
| A4 (FA-10) | Line-item definitions for `total_debt`, `total_equity`, `net_income`, `operating_income` | Approve the defaults in FA-10 | Step 3 |
| A5 (FA-20) | Sign-in identifier: username or email | Email | Step 1 |
| A6 (FA-19) | Session lifetime and idle timeout | 8 hours, sliding | Step 1 |
| A7 (FA-26) | Planned app name for workspaces | `workspaces` | Step 1 |
| A8 (D-07) | Retention: deletion grace period, audit-event retention, backup age-out | Approve the proposed defaults | Step 1 (audit events) |
| A9 (FA-08) | Login protection: built-in scoped throttle, or a lockout library dependency | Built-in throttle first | Step 1 |
| A10 (FA-12) | Push a branch to run CI; enable branch protection and private vulnerability reporting on GitHub | Approve | Before step 1 merges |
| A11 (FA-03) | How to provide PostgreSQL locally: start Docker Desktop with a free port, or create a dedicated role and database on an existing server | Docker on a free port; never the existing servers' default databases | Before step 1 merges |
| A12 (D-09, D-10) | Security and conduct contact address; DCO sign-off | Publish an address before accepting outside contributions | Before announcing the repository |

## 9. Readiness verdict

**Ready to begin MVP step 1 (workspace ownership and authorisation)** once A3, A5, A6, A7
and A9 are decided. Each is small and has a recommended default. Before step 1's first
migration merges, also:

1. Get a PostgreSQL run working (A11 or A10), so every model step is verified on the real database from the start.
2. Ideally complete the Python move (A1) first. It is cheaper before any app models and migrations exist.

Steps 2–5 additionally need A2 and A4. No finding requires re-architecting. The foundation's
layering, security defaults, dependency hygiene and calculation core are sound.

## 10. Changes made during this audit

- `backend/domain/calculations/metrics.py`, `precision.py`, `domain/validation/issues.py`: FA-01 out-of-range handling; FA-27 message wording.
- `backend/apps/core/middleware.py`, `apps/core/logging.py`: FA-14.
- `backend/config/settings/base.py` (comment, FA-06) and `test.py` (FA-22).
- `backend/pyproject.toml`: mypy `disallow_any_generics = false` for `tests.*` only.
- Tests: `tests/api/test_security_defaults.py` (new), plus additions to `test_health.py`, `test_settings.py` and `domain/test_calculations.py`.
- Docs: DATA_MODEL, DATABASE_CONVENTIONS, DATA_LIFECYCLE (FA-05); THREAT_MODEL, SECURITY_AND_PRIVACY, DATA_FLOW, LOCAL_SETUP (FA-06, FA-13); ERROR_HANDLING (FA-14); FINANCIAL_CALCULATION_CONVENTIONS (FA-01, version policy); TESTING_STRATEGY and QUALITY_GATES (counts; repaired a character-encoding corruption introduced in Phase 0); PRODUCT_SCOPE NFR-070 status; CHANGELOG.
- `.env.example`: port guidance (comment only).

No dependency was added or upgraded. Nothing was committed or pushed, no database was
created or modified other than the throwaway in-memory test database, and `LICENSE` is
untouched.

## 11. Follow-up (2026-10-27)

This section records what happened to the findings and decisions after the audit. The
sections above are left as they were found on 2026-10-25.

| Item | Outcome |
|---|---|
| FA-03, A11 | The Phase 0 foundation was pushed, and GitHub Actions ran the backend suite on PostgreSQL 17 for Python 3.10 and 3.13. Every job passed. Local runs still use SQLite in memory unless `FINLUME_TEST_DB_ENGINE=postgresql` is set. |
| FA-04, A1 (D-01) | Python floor raised to 3.12: `requires-python`, Ruff and mypy targets, locks re-compiled with `--python-version 3.12`, and a CI matrix of 3.12 and 3.13. The re-lock dropped only the 3.10-only pins. The local `.venv` was recreated on Python 3.13.17. All gates pass (126 tests), and the dev `pip-audit` is clean. Ruff's py312 rules turned `LineItem` and `IssueCode` into `StrEnum`. Their values and `.value` behaviour are unchanged, and `str()` now returns the value. |
| FA-12, A10 | CI is green. `.github/dependabot.yml` was added for pip, both npm apps and GitHub Actions. The actions moved to their Node 24 majors (`checkout@v5`, `setup-python@v6`, `setup-node@v5`) after the first run warned that Node 20 is deprecated. **Still open:** SHA-pinning the actions, and the repository settings (branch protection on `main`, private vulnerability reporting, Dependabot alerts, secret scanning). |
| A3 (FA-07), A5 (FA-20), A6 (FA-19), A9 (FA-08) | Decided in [ADR-0007](../decisions/ADR-0007-authentication-and-sessions.md): `401` with a `Session` challenge, email sign-in, an 8-hour sliding session, and built-in login throttles (5/minute per IP and per email). Implementation is part of step 1. |
| A7 (FA-26) | The app is named `workspaces`. The proposed ADR-0008 also brings `Organization` (in `organizations`) into MVP step 1, as the customer boundary. |
| §7 open question (can a business workspace outlive every owner?) | Answered by the proposed ADR-0008: no. The last owner cannot leave until ownership is transferred, and recovery after every owner is deactivated is an audited, operator-only command. |
| A8 (D-07) | The retention defaults in [DATA_LIFECYCLE §7](../data/DATA_LIFECYCLE_AND_RETENTION.md#7-retention-periods) are approved. |
| Still open | A2 (FA-02, before step 2), A4 (FA-10, before step 3) and A12 (before announcing the repository). |
