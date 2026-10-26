# Database Conventions

These rules apply to every Django model and migration in `backend/`. They are binding for
new code. Deviations need a reason recorded in the pull request, or an ADR if the deviation
is material. Logical entities are described in the [data model](DATA_MODEL.md).

## Database engines

| Engine | Use | Status |
|--------|-----|--------|
| PostgreSQL 17 | Production, self-hosted deployments, CI, recommended local development (`compose.yaml`) | Required in production. `config.settings.production` refuses any other engine |
| SQLite | Explicit opt-in for throwaway development trials (`FINLUME_DB_ENGINE=sqlite`), and the default for isolated local `pytest` runs (`FINLUME_TEST_DB_ENGINE`) | **Never for real financial data.** SQLite's `NUMERIC` affinity can store decimals as binary floating point, which loses precision beyond about 15 significant digits |

CI runs the test suite against PostgreSQL, and that run is authoritative. Tests that rely on
PostgreSQL-only behaviour (partial indexes, `jsonb` operators, exact `numeric` round-trips)
are marked `@pytest.mark.postgres`.

## Naming

| Object | Convention | Example |
|--------|------------|---------|
| Table | Django default `<app_label>_<model>` in snake_case; do not override `db_table` without a reason | `financial_records_financialfact` |
| Column | snake_case; foreign keys end in `_id` (Django default) | `entity_id`, `period_end` |
| Boolean | `is_` / `has_` prefix | `is_active` |
| Timestamp | `_at` suffix | `created_at`, `reviewed_at` |
| Date | `_date`, or a period-bound name | `period_start`, `period_end` |
| Constraint | `<app_label>_<model>_<purpose>` (stable; appears in migrations) | `accounts_user_email_ci_unique` |
| Index | `<table-abbrev>_<columns>_idx`, ≤ 30 characters | `fact_entity_item_end_idx` |
| Enumerations | Lowercase snake_case strings stored as `varchar` with a CHECK constraint (`models.TextChoices`) | `balance_sheet` |

Codes stored in the database (line-item codes, metric codes, issue codes, enum values) are
part of the persisted contract. They are never renamed or reused. Retire a code and add a
new one.

## Standard columns

| Column | Type | Rule |
|--------|------|------|
| `id` | `bigint` identity (`BigAutoField`, the `DEFAULT_AUTO_FIELD`) | Internal only: used for joins, never exposed by the API |
| `public_id` | `uuid`, `UNIQUE`, default `uuid4`, not editable | The only identifier in URLs and API payloads. Prevents enumeration and the leaking of record counts |
| `created_at` | `timestamptz`, default now | On every table |
| `updated_at` | `timestamptz`, updated automatically | Omitted on append-only tables (`AuditEvent`, completed analysis records) |

Implemented example: `accounts.User` has `public_id` and keeps Django's `id`.

## Data types

| Data | Django field | PostgreSQL type | Notes |
|------|--------------|-----------------|-------|
| Monetary amounts (raw and normalised) | `DecimalField(max_digits=30, decimal_places=6)` | `numeric(30,6)` | Up to 10²⁴ in base units with 6 decimal places. Never `FloatField` |
| Metric results | `DecimalField(max_digits=24, decimal_places=6)` | `numeric(24,6)` | Matches the engine's 6-dp quantisation |
| Currency | `CharField(max_length=3)` + CHECK `^[A-Z]{3}$` | `char(3)` / `varchar(3)` | ISO 4217 alphabetic code |
| Dates | `DateField` | `date` | Reporting periods are dates, not timestamps |
| Timestamps | `DateTimeField` (`USE_TZ = True`) | `timestamptz` | Stored in UTC. The settings use `TIME_ZONE = "UTC"` |
| Enumerations | `CharField` + `TextChoices` + CHECK | `varchar(n)` | Human-readable in the database and in backups |
| Hashes | `CharField(max_length=64)` | `char(64)` | Lowercase hex SHA-256 |
| Structured metadata | `JSONField` | `jsonb` | Only for genuinely schemaless data. Decimals inside JSON are stored as **strings** |
| Free text | `TextField` / `CharField(max_length=n)` | `text` / `varchar(n)` | Choose a bounded length when the domain has one |

Decimal values are never serialised as JSON numbers, whether in `jsonb` columns or in API
responses (`COERCE_DECIMAL_TO_STRING = True`).

## Keys, relationships and deletion

| Relationship | `on_delete` | Reason |
|--------------|-------------|--------|
| Owned child of its parent (statement → raw rows, run → metric results, workspace → memberships) | `CASCADE` | The child has no meaning without its parent |
| Provenance links (fact → raw row, fact → statement, run → input facts, statement → source document, statement → superseded version, report → run) | `RESTRICT` | Evidence cannot be deleted while anything outside the current deletion references it, yet a workspace cascade still succeeds. Do not use `PROTECT` here: it blocks even a cascade that deletes the referencing rows too |
| Actor references (`created_by`, `uploaded_by`, `reviewed_by`, audit `actor`) | `SET NULL` | Records survive account deletion; attribution is pseudonymised |

Workspace deletion is a service-layer operation that deletes in dependency order inside one
transaction. It does not rely on a single cascade (see
[Data lifecycle](DATA_LIFECYCLE_AND_RETENTION.md)).

## Tenancy scoping

- Every tenant-owned table has a non-null `workspace` foreign key, either directly or through an owned parent. Frequently queried tables (`FinancialStatement`, `FinancialFact`, `AnalysisRun`, `SourceDocument`, `Report`) have it **directly**, even though it is derivable, so every query can filter on it with an index.
- Querysets in API views always start from the requesting user's memberships (`.filter(workspace__memberships__user=request.user)` or an equivalent manager method). They never start from `Model.objects.all()`.
- An object outside the user's workspaces returns `404`, not `403`, so its existence is not disclosed.
- Shared reference data (for example, future market data) lives in separate tables without a `workspace` column and is read-only to users.

## Constraints

Integrity rules that can be expressed in the database are declared there
(`Meta.constraints`), not only in Python:

- `UniqueConstraint` for natural keys, for example `(statement, line_item)`. Use `Lower()` functional unique constraints for case-insensitive identity, as in the implemented `accounts_user_email_ci_unique`.
- Partial unique constraints (`condition=Q(...)`) for "only one active version" rules.
- `CheckConstraint` for enumerations, date order (`period_start <= period_end`), positive versions and currency format.
- Nullable columns only where "unknown" is a real state. A missing financial value is represented by the **absence of a fact row**, never by `NULL` in `FinancialFact.value` or by `0`.

## Indexes

Add an index when a query pattern needs it, and name it. Planned MVP indexes are listed with
each entity in the [data model](DATA_MODEL.md). Rules:

- Composite indexes start with the tenancy column (`workspace_id`) or the parent foreign key used for scoping.
- Use descending order on time columns for "latest first" lists.
- Do not index low-cardinality enumeration columns on their own.
- Each new index on a large table is checked with `EXPLAIN` in the pull request.

## Migrations

- Generated with `python manage.py makemigrations` and committed with the model change. CI fails on drift (`makemigrations --check --dry-run`), and a test also covers it.
- Migrations are created only for models that are designed and implemented. Placeholder models are never added.
- Review every migration for locking and data safety. On populated tables, add columns as nullable or with a database default, backfill in a separate data migration, then add constraints.
- Data migrations are idempotent and never contain real data.
- A migration that has been merged into `main` is never edited. Write a new migration instead.
- Destructive operations (dropping columns or tables) are split from code changes across two releases.
- Never run migrations against a database you have not identified. CI uses an ephemeral PostgreSQL service container.

## Transactions

- `ATOMIC_REQUESTS = True`: each HTTP request runs in one transaction, so a failed request leaves no partial writes. The health endpoint opts out with `transaction.non_atomic_requests`, so that a database outage produces a `503` rather than a `500`.
- Multi-step operations outside requests (management commands, future background jobs) use `transaction.atomic()` explicitly.
- Use `select_for_update()` when creating new statement versions, to prevent two concurrent restatements of the same statement.

## Raw SQL

Raw SQL is avoided. When it is necessary, it always uses query parameters, never string
formatting, and sits behind a function with a test that runs on PostgreSQL.
