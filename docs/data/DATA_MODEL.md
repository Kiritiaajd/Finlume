# Data Model

Conceptual and logical data model for Finlume. Status markers:

- **Implemented**: the table exists in a migration today.
- **MVP**: designed for Phase 1, but not yet a model or migration.
- **Future**: direction only; the design will be revisited before implementation.

Physical conventions (types, naming, indexes, constraints) are defined in
[Database conventions](DATABASE_CONVENTIONS.md). Deletion and retention behaviour is in
[Data lifecycle and retention](DATA_LIFECYCLE_AND_RETENTION.md). How the stored numbers are
calculated is in [Financial calculation conventions](FINANCIAL_CALCULATION_CONVENTIONS.md).

## 1. Design principles

1. **Separate domains get separate tables.** Business statements, personal transactions and investment holdings have different rules, permissions and lifecycles. They are not forced into one generic "financial record" table.
2. **The workspace is the tenancy boundary.** Every tenant-owned row is reachable from exactly one workspace, and frequently queried tables carry a direct `workspace` foreign key so authorization filters are simple and indexable.
3. **Raw input is kept separate from normalised facts.** What the user entered or uploaded is stored as-is. Normalised facts are derived from it and point back to it.
4. **Provenance is never broken.** Foreign keys along the provenance chain use Django's `on_delete=RESTRICT`. A source, statement version or fact cannot be deleted while something outside the same deletion still references it. Unlike `PROTECT`, `RESTRICT` still lets a whole workspace (or a user's personal workspace) be deleted in one cascade, because every referencing row is deleted with it. `PROTECT` would raise `ProtectedError` in that case, even inside a correct cascade.
5. **Analysis results are append-only.** A completed analysis run is never edited. A correction produces a new statement version and a new run.
6. **Only what the MVP needs is implemented.** Future entities are documented here so the MVP design does not block them, but they get no tables yet.

## 2. Entity overview

| Entity | Planned app | Status | Purpose |
|--------|-------------|--------|---------|
| `User` | `accounts` | **Implemented** | Authentication identity |
| `Organization` | `organizations` | MVP | Customer boundary; owns organization workspaces |
| `OrganizationMembership` | `organizations` | MVP | User's role in an organization (`admin` or `member`) |
| `Workspace` | `workspaces` | MVP | Tenancy and permission boundary: a user's personal workspace, or an organization workspace |
| `WorkspaceMembership` | `workspaces` | MVP | User's role in a workspace; the only source of workspace access |
| `ReportingEntity` | `financial_records` | **Implemented** (step 2a) | The business, person or company whose statements are analysed |
| `SourceDocument` | `documents` | **Implemented** (manual entry in step 2a, CSV files in step 4) | Where figures came from: manual entry session or uploaded file |
| `FinancialStatement` | `financial_records` | **Implemented** (step 2a) | One statement for one entity, one period, one version |
| `StatementLineItem` | `financial_records` | **Implemented** (step 2a) | A raw row exactly as entered or uploaded |
| `FinancialFact` | `financial_records` | **Implemented** (step 2a) | A verified, normalised figure in base currency units |
| `AnalysisRun` | `analysis` | **Implemented** (step 5a) | One immutable execution of the calculation engine |
| `MetricResult` | `analysis` | **Implemented** (step 5a) | One metric value produced by a run |
| `AnalysisIssue` | `analysis` | **Implemented** (step 5a) | A validation or calculation issue produced by a run |
| `Report` | `reports` | **Implemented** (step 5b) | A saved, titled view of one or more analysis runs |
| `AuditEvent` | `audit` | MVP | Who did what, when; contains no financial values |
| `Team`, `TeamMembership` | `organizations` | Future | Manage workspace memberships for a group ([ADR-0008](../decisions/ADR-0008-organizations-and-workspace-tenancy.md) §5) |
| `ExtractionCandidate` | `ingestion` | Future (Phase 2) | A value extracted from a PDF, awaiting human review |
| `ExplanationRecord` | `explanations` | Future (Phase 3) | An AI explanation and the stored results it cites |
| Personal finance entities | `personal_finance` | Future (Phase 4) | `Account`, `Transaction`, `Category`, `Budget` |
| Investment entities | `investments`, `market_data` | Future (Phase 5) | `Security`, `Listing`, `PriceBar`, `Portfolio`, `Holding`, `Trade`, provider snapshots |

## 3. Relationships (MVP)

```mermaid
erDiagram
    USER ||--o{ ORGANIZATION_MEMBERSHIP : has
    ORGANIZATION ||--o{ ORGANIZATION_MEMBERSHIP : grants
    ORGANIZATION ||--o{ WORKSPACE : "owns (organization workspace)"
    USER |o--o| WORKSPACE : "owns (personal workspace)"
    USER ||--o{ WORKSPACE_MEMBERSHIP : has
    WORKSPACE ||--o{ WORKSPACE_MEMBERSHIP : grants
    WORKSPACE ||--o{ REPORTING_ENTITY : contains
    WORKSPACE ||--o{ SOURCE_DOCUMENT : owns
    REPORTING_ENTITY ||--o{ FINANCIAL_STATEMENT : reports
    SOURCE_DOCUMENT ||--o{ FINANCIAL_STATEMENT : "supplies"
    FINANCIAL_STATEMENT ||--o{ STATEMENT_LINE_ITEM : "contains raw rows"
    FINANCIAL_STATEMENT |o--o| FINANCIAL_STATEMENT : supersedes
    STATEMENT_LINE_ITEM ||--o| FINANCIAL_FACT : "normalised into"
    REPORTING_ENTITY ||--o{ FINANCIAL_FACT : describes
    REPORTING_ENTITY ||--o{ ANALYSIS_RUN : "analysed by"
    ANALYSIS_RUN }o--o{ FINANCIAL_FACT : "used as input"
    ANALYSIS_RUN ||--o{ METRIC_RESULT : produces
    ANALYSIS_RUN ||--o{ ANALYSIS_ISSUE : reports
    WORKSPACE ||--o{ REPORT : owns
    REPORT }o--o{ ANALYSIS_RUN : presents
    WORKSPACE ||--o{ AUDIT_EVENT : records
    USER ||--o{ AUDIT_EVENT : "acts in"
```

## 4. Entities

Every entity below also has the standard columns from
[Database conventions](DATABASE_CONVENTIONS.md#standard-columns): `id` (internal),
`public_id` (UUID, used in the API), `created_at` and `updated_at`. They are not repeated in
each table. An append-only entity has no `updated_at`.

### 4.1 User (Implemented)

App `accounts`, table `accounts_user`. Extends Django's `AbstractUser`.

| Field | Type | Notes |
|-------|------|-------|
| `id` | bigint PK | Internal; never exposed through the API |
| `public_id` | uuid, unique | API identifier |
| `username` | varchar(150), unique | Django default |
| `email` | varchar(254) | Unique **case-insensitively** through `UniqueConstraint(Lower("email"), name="accounts_user_email_ci_unique")` |
| `password` | varchar(128) | Django password hash; never logged |
| `first_name`, `last_name`, `is_staff`, `is_active`, `is_superuser`, `last_login`, `date_joined` | Django defaults | |

Ownership: a user owns no financial data directly. Data belongs to workspaces, and users act
on it through memberships.

### 4.2 Organization and OrganizationMembership (MVP)

The customer boundary ([ADR-0008](../decisions/ADR-0008-organizations-and-workspace-tenancy.md)).
Any signed-in user may create an organization and becomes its admin. **Organization
membership never grants access to workspace data**, not even for admins.

`Organization`:

| Field | Type | Notes |
|-------|------|-------|
| `name` | varchar(200) | |
| `created_by` | FK → User, `SET NULL`, nullable | |

`OrganizationMembership`:

| Field | Type | Notes |
|-------|------|-------|
| `organization` | FK → Organization, `CASCADE` | |
| `user` | FK → User, `CASCADE` | |
| `role` | varchar(16) | `admin` or `member` (CHECK) |

Constraints: `UNIQUE (user, organization)`, which also serves "my organizations". Application
logic keeps at least one admin.

| Organization role | Manage organization and its members | Create a workspace in it | Read its workspaces |
|---|---|---|---|
| member | | ✓ (becomes owner) | only through workspace membership |
| admin | ✓ | ✓ (becomes owner) | only through workspace membership |

Status, settings and teams are deliberately absent until a feature needs them.

### 4.3 Workspace and WorkspaceMembership (MVP)

The tenancy and permission boundary for all financial data. A workspace is either a user's
**personal workspace** (exactly one per user, created at registration, never shared) or an
**organization workspace**.

`Workspace`:

| Field | Type | Notes |
|-------|------|-------|
| `name` | varchar(200) | |
| `organization` | FK → Organization, `CASCADE`, nullable | Set for organization workspaces |
| `personal_owner` | FK → User, `CASCADE`, nullable, unique | Set for personal workspaces |
| `created_by` | FK → User, `SET NULL`, nullable | |
| `base_currency` | char(3), nullable | Default currency for new statements; display only, no conversion. Added in MVP step 3 |

Constraints: `personal_owner` is `UNIQUE`, and
`CHECK ((organization IS NULL) <> (personal_owner IS NULL))`: exactly one of the two is set.
The kind is derived from which link is set, so there is no `kind` column that could disagree.

`WorkspaceMembership`:

| Field | Type | Notes |
|-------|------|-------|
| `workspace` | FK → Workspace, `CASCADE` | |
| `user` | FK → User, `CASCADE` | |
| `role` | varchar(16) | `owner`, `editor` or `viewer` (CHECK) |

Constraints: `UNIQUE (user, workspace)`. This is the index behind the per-request access
check. Django's FK index on `workspace` serves member lists.

Invariants kept by the application layer, inside transactions
([tenancy plan §3](../development/TENANCY_IMPLEMENTATION_PLAN.md#invariants-enforced-in-use-cases-and-covered-by-tests)):

- A personal workspace has exactly one member, its owner.
- A user is a member of an organization workspace only while they are a member of that organization.
- Every workspace keeps at least one owner.
- Creating a workspace makes its creator the owner in the same transaction.

| Role | Read | Create/edit statements and runs | Manage members | Delete workspace |
|------|------|---------------------------------|----------------|------------------|
| viewer | ✓ | | | |
| editor | ✓ | ✓ | | |
| owner | ✓ | ✓ | ✓ | ✓ (MVP step 8) |

**Why one table for personal and organization workspaces?** Tenancy, membership and audit
rules are the same for both. The domain data they hold differs and lives in separate tables
(for example, personal-finance transactions in Phase 4 never share a table with business
statements).

### 4.4 ReportingEntity (Implemented)

The subject of analysis: the user's own business, a client's business or a researched
listed company.

| Field | Type | Notes |
|-------|------|-------|
| `workspace` | FK → Workspace, `CASCADE` | |
| `name` | varchar(200) | |
| `entity_type` | varchar(16) | `business`, `individual` or `listed_company` (CHECK) |
| `default_currency` | varchar(3), blank when none | Suggested currency for new statements; `''` or `^[A-Z]{3}$` (CHECK) |
| `fiscal_year_end_month` | smallint, nullable | 1–12 (CHECK) |

Constraints: `UNIQUE (workspace, name)` (exact, case-sensitive).

`identifiers` (ticker, ISIN or registration number) is added in Phase 5, when something
interprets it.

### 4.5 SourceDocument (Implemented)

Records where figures came from. Every statement has exactly one source.

| Field | Type | Notes |
|-------|------|-------|
| `workspace` | FK → Workspace, `CASCADE` | |
| `kind` | varchar(16) | `manual_entry` or `csv_upload` (CHECK); later `pdf` (Phase 2) and `provider` (Phase 5) |
| `created_by` | FK → User, `SET NULL`, nullable | Who entered or uploaded it. `created_at` is the upload time |
| `original_filename` | varchar(255), blank for manual entry | Display only; never used as a storage path |
| `content_type` | varchar(100), blank for manual entry | Detected from the content (`text/csv` once it decodes as UTF-8 text), not trusted from the client |
| `size_bytes` | bigint, null for manual entry | |
| `sha256` | char(64) as varchar, blank for manual entry | Lowercase hex fingerprint of the stored bytes |
| `storage_key` | varchar(255), blank for manual entry | Random key in the `private_documents` storage, `documents/<workspace>/<random>`; never derived from the filename |
| `idempotency_key` | uuid, nullable | The client's `Idempotency-Key` for the upload that created it |

Constraints:

- `CHECK`: manual entry has no file columns; a file kind has a size, a 64-character lowercase hex `sha256` and a `storage_key` (`documents_sourcedocument_file_fields`).
- Partial `UNIQUE (workspace, created_by, idempotency_key)` where the key is set.

Index: `(workspace, sha256)`, which detects re-uploads of the same file (a warning, not a
rejection).

A CSV row keeps its file line number in `StatementLineItem.source_reference` (`line 7`),
so every fact traces to its line, its statement version and this document.

Files are stored only through `PrivateFileSystemStorage`. This is **Implemented**:
`url()` raises `PublicURLNotAllowedError` and files are written with mode `0o600`.

### 4.6 FinancialStatement (Implemented)

One statement type for one entity and one period, at one version.

| Field | Type | Notes |
|-------|------|-------|
| `workspace` | FK → Workspace, `CASCADE` | Denormalised for scoping |
| `entity` | FK → ReportingEntity, `RESTRICT` | |
| `statement_type` | varchar(24) | `income_statement`, `balance_sheet` or `cash_flow` (CHECK) |
| `period_start`, `period_end` | date | `CHECK (period_start <= period_end)`; balance sheet figures are as of `period_end` |
| `period_type` | varchar(16) | `annual`, `half_year`, `quarter`, `month` or `other` (CHECK) |
| `currency` | varchar(3) | ISO 4217, `CHECK (currency ~ '^[A-Z]{3}$')` |
| `reported_scale` | varchar(16) | `units`, `thousands`, `lakhs`, `millions`, `crores` or `billions` (CHECK) |
| `source_document` | FK → SourceDocument, `RESTRICT` | |
| `status` | varchar(16) | `draft` (default), `validated` or `superseded` (CHECK) |
| `version` | integer ≥ 1 | Default 1 |
| `previous_version` | integer, generated (`version - 1`, stored) | Computed by the database; used by the restatement key below |
| `supersedes` | FK → self, `RESTRICT`, nullable, unique | The previous version this one restates: exactly version `version - 1` of the same statement |
| `restatement_reason` | text, blank unless restating | Required when `supersedes` is set, with at least one non-whitespace character, and blank otherwise (CHECK) |

The statement type, period type and scale codes, and the line-item codes below, are taken
from `domain.financial_statements` (`StatementType`, `PeriodType`, `Scale`, `LineItem`),
so the database and the engine share one taxonomy. A change there shows up as a pending
migration.

Constraints:

- `UNIQUE (entity, statement_type, period_start, period_end, version)`.
- **Current versions.** Per (`entity`, `statement_type`, `period_start`, `period_end`), two partial unique indexes allow **at most one `validated` version** (the one analyses use) and **at most one `draft`**. A restatement can therefore be drafted as version *n + 1* while version *n* stays validated and in use. Validating the draft marks version *n* `superseded` in the same transaction (step 3). These indexes cannot be deferred, so version *n* is superseded **before** version *n + 1* is marked validated. Any number of superseded versions may exist. Analyses use the validated version, never a draft.
- `CHECK ((version = 1) = (supersedes IS NULL))`, written as `(version = 1 AND supersedes IS NULL) OR (version > 1 AND supersedes IS NOT NULL)`, plus `CHECK (version >= 1)`.
- A restatement restates exactly the previous version of the same statement: same workspace, entity, statement type and period, and `version - 1`. A version therefore cannot restate itself, skip a version or restate a later one ([cross-row consistency](#cross-row-consistency-postgresql)).

Index: `(workspace, entity, period_end DESC)` for dashboard lookups.

### 4.7 StatementLineItem (Implemented)

A raw input row, exactly as the user provided it.

| Field | Type | Notes |
|-------|------|-------|
| `statement` | FK → FinancialStatement, `CASCADE` | Raw rows belong to their statement version |
| `row_number` | integer ≥ 1 | Order in the source (CHECK) |
| `label` | varchar(255) | Label as entered or as it appeared in the CSV |
| `line_item_code` | varchar(64), blank when unmapped | Mapped canonical code (see the [taxonomy](FINANCIAL_CALCULATION_CONVENTIONS.md#4-line-item-taxonomy-implemented)); `''` or a taxonomy code (CHECK) |
| `reported_amount` | numeric(30,6), nullable | In the statement's `reported_scale`; null when the source cell was blank |
| `raw_value` | varchar(64), may be blank | Original text, kept for audit (for example `"(1,234.5)"`) |
| `source_reference` | varchar(64), may be blank | For example `row 14` or `B14`; later a PDF page/region |

Constraints: `UNIQUE (statement, row_number)`. A partial unique index on
(`statement`, `line_item_code`) where `line_item_code <> ''` ensures a code is mapped
at most once per statement. Whether a code belongs to the statement's type (for example,
`revenue` only on an income statement) is checked by the step 3 input validation.

### 4.8 FinancialFact (Implemented)

A verified, normalised figure. This is the only input the calculation engine accepts.
Persisted facts are loaded into the domain's `FinancialFactSet` (**Implemented**).

| Field | Type | Notes |
|-------|------|-------|
| `workspace` | FK → Workspace, `CASCADE` | |
| `entity` | FK → ReportingEntity, `RESTRICT` | |
| `statement` | FK → FinancialStatement, `RESTRICT` | The exact statement version |
| `line_item` | varchar(64) | Canonical code; a taxonomy code (CHECK) and equal to its raw row's code |
| `period_start`, `period_end`, `period_type` | | Copied from the statement for indexing, and kept equal to it |
| `currency` | varchar(3) | Copied from the statement, and kept equal to it |
| `value` | numeric(30,6) | **Base currency units**, signed according to the sign convention |
| `derived_from` | FK → StatementLineItem, `RESTRICT`, unique | Provenance link, to a mapped row of the same statement |
| `review_status` | varchar(16) | `unreviewed`, `confirmed` or `rejected` (CHECK); manual and confirmed-CSV facts start as `confirmed` |
| `reviewed_by` | FK → User, `SET NULL`, nullable | |
| `reviewed_at` | timestamptz, nullable | |

Constraints: `UNIQUE (statement, line_item)`. Index:
`(entity, line_item, period_end)` for multi-period queries.

### Cross-row consistency (PostgreSQL)

Single-column foreign keys cannot keep related rows in one workspace. Django 5.2 has no
composite foreign keys, so migrations `financial_records.0002` and `0003` add them in SQL on
PostgreSQL. Each one references a `*_key` unique constraint declared on the target model:

| Constraint | Columns → referenced columns | Guarantees |
|---|---|---|
| `…financialstatement_entity_same_workspace` | `(workspace, entity)` → entity `(workspace, id)` | A statement's entity is in its workspace |
| `…financialstatement_source_same_workspace` | `(workspace, source_document)` → document `(workspace, id)` | Its source document is too |
| `…financialstatement_supersedes_same_key` | `(workspace, entity, statement_type, period_start, period_end, previous_version, supersedes)` → statement `(…, version, id)` | A restatement restates the previous version of the same statement (migration `0003`) |
| `…financialfact_matches_statement` | `(workspace, entity, period_start, period_end, period_type, currency, statement)` → statement | A fact's copied columns equal its statement's, so a statement with facts cannot change them |
| `…financialfact_derived_from_same_statement` | `(statement, derived_from, line_item)` → line item `(statement, id, line_item_code)` | A fact derives from a mapped row of its own statement, with the same code |

A line item has no `workspace` column. It reaches its workspace through its statement, and
the last key keeps its fact in the same one.

The keys are `DEFERRABLE INITIALLY DEFERRED`, like Django's own foreign keys, and use
`ON DELETE NO ACTION`. Django's `RESTRICT` handling decides what may be deleted, and a
workspace cascade can remove rows in any order within its transaction. They are checked
at commit, or earlier with `SET CONSTRAINTS ALL IMMEDIATE`, which is what
`connection.check_constraints()` does. SQLite, which is never used for real data, does not
get them.

### 4.9 AnalysisRun (Implemented)

One execution of `domain.calculations.run_statement_analysis`. A run is **append-only**: it
has `public_id` and `created_at` but no `updated_at`, and the model refuses to save an
existing run or delete one by itself (`ImmutableRecordError`). Runs disappear only with
their workspace. A correction is a new statement version and a new run.

| Field | Type | Notes |
|-------|------|-------|
| `workspace` | FK → Workspace, `CASCADE` | |
| `entity` | FK → ReportingEntity, `RESTRICT` | In the run's workspace (PostgreSQL composite key, `analysis.0002`) |
| `period_start`, `period_end`, `period_type`, `currency` | | The fact set's period and currency (CHECKs as on statements) |
| `engine_version` | varchar(32) | `ENGINE_VERSION` at run time, currently `0.1.0` |
| `input_fingerprint` | char(64) as varchar | SHA-256 of the canonicalised input facts, lowercase hex (CHECK); see [conventions](FINANCIAL_CALCULATION_CONVENTIONS.md#10-reproducibility-and-versioning) |
| `created_by` | FK → User, `SET NULL` | |
| `idempotency_key` | uuid, nullable | Partial `UNIQUE (workspace, created_by, idempotency_key)` |

There is no `status` or `completed_at`. A run is saved only once it has completed, so
`created_at` is its completion time. Inputs that cannot be assembled are refused before
anything is saved (decided 2026-10-27). A status column arrives with background jobs
(Phase 2).

A join table `AnalysisRunInputFact (run, fact)`, `UNIQUE (run, fact)` with `RESTRICT` on
`fact`, records exactly which facts were used, so those facts and their statements can never
be deleted while the run exists. Indexes: `(workspace, entity, created_at DESC)`, and
`(entity, input_fingerprint, engine_version)` to find equivalent runs.

### 4.10 MetricResult (Implemented)

Append-only, like its run.

| Field | Type | Notes |
|-------|------|-------|
| `run` | FK → AnalysisRun, `CASCADE` | |
| `position` | smallint | Report order, as in `RATIO_DEFINITIONS` |
| `metric_code` | varchar(64) | A `RATIO_DEFINITIONS` code, for example `gross_margin` (CHECK) |
| `value` | numeric(24,6), nullable | Null means not computable; never zero for a missing input |
| `unit` | varchar(16) | `ratio` (CHECK) |
| `methodology` | text | Copied from the definition at run time |
| `inputs` | jsonb | `{line_item_code: "decimal string"}`; decimals are stored as strings, never as JSON floats |

Constraints: `UNIQUE (run, metric_code)`.

### 4.11 AnalysisIssue (Implemented)

Append-only, like its run.

| Field | Type | Notes |
|-------|------|-------|
| `run` | FK → AnalysisRun, `CASCADE` | |
| `position` | smallint | Validation issues first, then each metric's issues; `UNIQUE (run, position)` |
| `metric_code` | varchar(64), blank | Blank for validation issues about the whole fact set (CHECK: blank or a metric code) |
| `code` | varchar(64) | `IssueCode` value, for example `balance_sheet_imbalance` (CHECK) |
| `severity` | varchar(16) | `info`, `warning` or `error` (CHECK) |
| `message` | text | |
| `line_items` | jsonb | List of line-item codes |

### 4.12 Report (Implemented)

| Field | Type | Notes |
|-------|------|-------|
| `workspace` | FK → Workspace, `CASCADE` | |
| `title` | varchar(200) | |
| `notes` | text, may be blank | User commentary, clearly separated from calculated values |
| `runs` | M2M → AnalysisRun through `ReportRun` | Ordered by `ReportRun.position`; at most 50 runs |
| `created_by` | FK → User, `SET NULL` | |

`ReportRun (workspace, report, run, position)`: `report` is `CASCADE` and `run` is
`RESTRICT`, so a run in a report cannot be deleted. `UNIQUE (report, run)` and
`UNIQUE (report, position)` apply. On PostgreSQL, composite keys tie both the report and the
run to the row's `workspace`, so a report can only list runs of its own workspace
(`reports.0002`, using the `(workspace, id)` keys on `Report` and `AnalysisRun`).
Index: `(workspace, created_at DESC)`.

A report stores no calculated values. It is rendered live from its immutable runs, so it can
never drift from them, and each run shows `uses_superseded_statement` once its inputs were
restated. Exported PDFs or images are generated on demand and are not stored.

### 4.13 AuditEvent (MVP)

Append-only. Never contains financial values, document contents or credentials.

| Field | Type | Notes |
|-------|------|-------|
| `occurred_at` | timestamptz | |
| `actor` | FK → User, `SET NULL`, nullable | Pseudonymised when the account is deleted |
| `actor_label` | varchar(64) | A stable pseudonym, so events stay attributable after deletion |
| `workspace` | FK → Workspace, `SET NULL`, nullable | |
| `action` | varchar(64) | For example `statement.created`, `analysis.run`, `membership.role_changed`, `organization.member_removed`, `workspace.ownership_recovered`, `auth.login_failed` |
| `target_type` | varchar(64) | For example `financial_statement` |
| `target_public_id` | uuid, nullable | |
| `request_id` | varchar(64) | Matches the `X-Request-ID` response header |
| `metadata` | jsonb | Non-financial context only, for example `{"version": 2}` |

Index: `(workspace, occurred_at DESC)`, `(actor, occurred_at DESC)`.

## 5. Provenance chain

```text
Source → Extracted value → Validation/review → Normalised financial fact → Versioned calculation → Result
```

| Step | MVP representation | Key guarantee |
|------|--------------------|---------------|
| Source | `SourceDocument` (manual entry session or CSV file with SHA-256) | The original bytes are kept privately and fingerprinted |
| Extracted value | `StatementLineItem` (`raw_value`, `reported_amount`, `source_reference`) | The input is kept verbatim; nothing is overwritten |
| Validation/review | Mapping review, domain validation issues, `FinancialFact.review_status` | Only confirmed facts feed calculations |
| Normalised fact | `FinancialFact.value` in base units, linked by `derived_from` | Normalisation is exact (`normalize_amount`) |
| Versioned calculation | `AnalysisRun` (`engine_version`, `input_fingerprint`, input fact links) | Same inputs and version give the same output |
| Result | `MetricResult`, `AnalysisIssue` | Each result carries its methodology and input values |

Phase 2 (PDF) adds `ExtractionCandidate` between Source and Extracted value: page, bounding
region, extractor name and version, and confidence. Candidates become `StatementLineItem`
rows only after a human confirms them.

## 6. Handling financial data specifics

| Concern | MVP rule |
|---------|----------|
| **Currency** | One ISO 4217 currency per statement. Facts and runs carry the currency. The engine never mixes currencies, and there is no FX conversion (decision D-03). |
| **Units and scales** | `reported_amount` stays in the reported scale. `FinancialFact.value` is always in base units, converted exactly by powers of ten. |
| **Reporting periods** | Explicit start and end dates plus a period type. A balance sheet is stored against the period it closes (the same start, end and type as the income statement), and its facts are as of `period_end`. An analysis combines facts with identical period bounds and type only. |
| **Assembling an analysis input** | Rule A2 ([FOUNDATION_AUDIT FA-02](../architecture/FOUNDATION_AUDIT.md#fa-02--no-rule-for-assembling-one-fact-set-from-separate-statements-approved)), implemented by `services.statement_analysis.assemble_analysis_input`: for one entity and period, the **validated** version of each statement type and its `confirmed` facts. A missing statement type is allowed. Statements in different currencies, or no validated statement at all, are refused (`409 conflict`). |
| **Missing data** | An absent fact means unknown. It is never stored or treated as zero. Blank cells give `reported_amount = NULL` and no fact. |
| **Restatements** | A new `FinancialStatement` version with `supersedes` and a reason, drafted while the previous version stays validated. Old facts and runs stay intact. New analyses use the latest **validated** version, never a draft restatement. |
| **Rounding** | Inputs are stored exactly as given, up to 6 decimal places. Results are quantised to 6 decimal places with half-even rounding. Display rounding happens in the client only. |
| **Reconciliation** | Validation checks (balance sheet identity and gross-profit subtotal, with 0.1 % relative tolerance) produce persisted `AnalysisIssue` warnings. They never auto-correct data. |

## 7. Future entities (direction only)

These get no tables until their phase begins, and each lives in its own app with its own
rules.

- **Personal finance (Phase 4):** `Account` (bank, card, cash, loan; currency), `Transaction` (date, amount, description, category, import batch, source row reference), `Category` (hierarchical, per workspace), `Budget`. Imported transactions follow the same provenance pattern: an import file as a `SourceDocument` and raw rows kept.
- **Bank feeds (unscheduled):** connection metadata only. Any credentials or tokens stay with a provider and are never stored in plaintext.
- **Investments (Phase 5):** `Security`, `Listing` (exchange, ticker), `PriceBar` (date, OHLC, currency, provider), `Portfolio`, `Holding`, `Trade`. Market data is shared reference data, not tenant data. It is held in separate tables with provider provenance and licence notes.
- **AI explanations (Phase 3):** `ExplanationRecord` (run, provider, model, prompt template version, output text, cited `MetricResult` IDs, created_by). An explanation can only cite stored results.
- **Background work (Phase 2):** `ImportJob` or extraction-job records if they become necessary.
