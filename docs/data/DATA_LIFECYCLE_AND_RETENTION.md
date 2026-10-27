# Data Lifecycle and Retention

How Finlume creates, changes, exports and deletes data, and how long it keeps data.

> **Status.** The retention periods below are the **approved defaults** (decision D-07 in
> the [product scope](../product/PRODUCT_SCOPE.md#10-unresolved-decisions), approved
> 2026-10-27). None of the deletion or export features described here are
> implemented yet. They are MVP requirements (FR-054, FR-055, NFR-022). Self-hosters
> control their own instance and can change any period.

## 1. Principles

1. **Collect only what an analysis needs.** No telemetry, analytics or third-party tracking by default.
2. **The user controls their financial data.** Workspace owners can export and delete everything in their workspace.
3. **Evidence is never edited in place.** Corrections create new versions, so past analyses remain explainable.
4. **Deletion is real.** Deleting financial data removes database rows and private files. Data is not just hidden behind a flag.
5. **Audit trails outlive content, not people.** Audit events keep minimal, non-financial metadata, and actors are pseudonymised when their account is deleted.

## 2. Data categories

| Category | Examples | Contains financial values | Sensitivity |
|----------|----------|---------------------------|-------------|
| Identity | `User` (username, email, password hash) | No | Personal data |
| Tenancy | `Workspace`, `Membership` | No | Low to moderate |
| Source files | CSV uploads in private storage; later PDFs | **Yes** | High |
| Financial records | `FinancialStatement`, `StatementLineItem`, `FinancialFact` | **Yes** | High |
| Analysis results | `AnalysisRun`, `MetricResult`, `AnalysisIssue`, `Report` | **Yes** (derived) | High |
| Audit | `AuditEvent` | No (by rule) | Moderate |
| Operational | Application logs, request IDs | No (by rule) | Moderate |
| Backups | Database dumps, storage snapshots | **Yes** | High |

## 3. Lifecycle by entity

| Entity | Created | Modified | Superseded / archived | Deleted |
|--------|---------|----------|-----------------------|---------|
| `SourceDocument` + file | On manual entry or upload | Never; the file is immutable | — | With its workspace, or explicitly once no statement references it (`RESTRICT`) |
| `FinancialStatement` (draft) | Manual entry or CSV import | Freely while in `draft` | — | Editors can delete drafts, together with their raw rows and facts |
| `FinancialStatement` (validated) | Draft confirmed | **Never edited**; corrections create a new version | Status becomes `superseded` when a newer version is validated | Only with its workspace, or by an owner after the runs that depend on it are deleted |
| `StatementLineItem` | With the statement | Only while the statement is a draft | Follows the statement | With the statement (`CASCADE`) |
| `FinancialFact` | When raw rows are confirmed | `review_status` only | Follows the statement version | With the statement version, once no run references it |
| `AnalysisRun` and its results | When analysis runs | **Never** after completion | Older runs remain and are labelled with their engine version | By an editor or owner (if no report references the run), or with the workspace |
| `Report` | Saved by the user | Title, notes, run list | — | By an editor or owner, or with the workspace |
| `AuditEvent` | On audited actions | **Never** | — | After the retention period |

## 4. Restatements and corrections

A correction to a validated statement never overwrites it:

1. A new `FinancialStatement` is created with `version = n + 1`, `supersedes` pointing to version `n`, and a required `restatement_reason`.
2. Once the new version is validated, version `n` becomes `superseded`. A partial unique constraint guarantees that only one version is non-superseded.
3. Existing analysis runs keep their links to version `n`'s facts, so they reproduce exactly.
4. New analyses use the latest non-superseded version. The dashboard shows when a newer version exists than the one a saved analysis used.

## 5. Export (MVP, FR-054)

Workspace owners can export the whole workspace as a ZIP file containing:

- statements, raw rows and facts as CSV (decimal values as plain decimal strings, with currency and scale columns);
- analysis runs, metric results and issues as JSON, including engine version and input fingerprint;
- the original source files.

Exports are generated on request, streamed to the user, and not kept on the server. An
`export.created` audit event is recorded.

## 6. Deletion

### 6.1 Workspace deletion (MVP, FR-055)

- Only an owner can request it. The owner must re-enter the workspace name to confirm.
- A grace period of **30 days** by default, configurable and possibly 0. During the grace period the workspace is locked (read-only, hidden from lists) and the deletion can be cancelled.
- When the grace period ends (or immediately if it is 0), a service operation deletes everything inside one database transaction, in dependency order: reports → analysis results and runs → facts → raw rows → statements → source documents → entities → memberships → workspace.
- Private files are deleted after the transaction commits (`transaction.on_commit`). If deleting a file fails, it is logged by storage key (never by content) and retried by a cleanup command, so orphaned files cannot accumulate silently.
- A `workspace.deleted` audit event is recorded without the workspace's financial content.

### 6.2 Organization deletion (MVP step 8)

- Only an organization admin can request it. It applies §6.1 to every workspace of the organization, then deletes its memberships and the organization in the same transaction.
- An `organization.deleted` audit event is recorded.

### 6.3 Account deletion

- A user who is the only owner of an organization workspace, or the only admin of an organization, must first transfer that role or delete the workspace or organization.
- The user's personal workspace is deleted as in §6.1.
- The `User` row is deleted. `created_by`, `uploaded_by` and `reviewed_by` references in other workspaces become `NULL`, and audit events keep only the stable pseudonym in `actor_label`.

Until these workflows exist, the Django admin cannot delete users or tenancy records
([ADR-0008](../decisions/ADR-0008-organizations-and-workspace-tenancy.md) §7).

### 6.4 Individual records

Editors can delete draft statements, unreferenced source documents, analysis runs that no
report references, and reports. `RESTRICT` foreign keys stop deletions that would break the
provenance chain. The API returns a `409` with the blocking references, and does not cascade
silently.

## 7. Retention periods

| Data | Default retention | Configurable by self-hosters | Notes |
|------|-------------------|------------------------------|-------|
| Financial data and source files | Until the user deletes them | — | No automatic expiry of user data |
| Workspace deletion grace period | 30 days | Yes (0 = immediate) | |
| `AuditEvent` | 1 year | Yes | Purged by a scheduled management command |
| Application logs | 30 days | Yes (log infrastructure) | Logs must not contain financial values |
| Database and storage backups | Age out within 35 days | Yes | Deleted data therefore disappears from backups within 35 days. This is disclosed to users |
| Generated exports | Not stored | — | Streamed only |
| Sessions | 8 hours of inactivity, sliding ([ADR-0007](../decisions/ADR-0007-authentication-and-sessions.md), from MVP step 1); expired rows cleared with `clearsessions` | Yes | Django's default of 2 weeks applies until step 1 |

## 8. Logging and observability boundaries

- Logs include the request ID, route, status, latency and user `public_id` where relevant. They **never** include amounts, statement contents, file contents, passwords, tokens or the full query strings of financial endpoints.
- SQL query logging (`django.db.backends`) is set to `WARNING` by default because SQL parameters can contain financial values. This is implemented in `config/settings/base.py`.
- API errors return only a safe message and the request ID. Internal exception text never reaches the client. This is implemented in `api/exceptions.py`.

## 9. Test and sample data

- Fixtures, tests, screenshots and documentation use **fictional** figures only. Real company filings may be used only if they are public and attributed, and never in automated tests.
- Real user data must never be copied into development, CI or issue reports.

## 10. Future phases

- **Phase 2 (PDF ingestion):** extraction candidates that are rejected during review are deleted with their document. Original PDFs follow the source-file rules above.
- **Phase 3 (AI):** explanation records follow their analysis run's lifecycle. If an external AI provider is enabled, the data sent and the provider's own retention terms must be shown to the user before the first use.
- **Phase 4 (personal finance):** imported transactions follow the financial-data rules. Bank connection tokens (if ever supported) are revoked at the provider when the connection is deleted.
- **Phase 5 (market data):** shared reference data follows the provider's licence terms, not user retention rules.
