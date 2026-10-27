# API conventions

The Finlume web and mobile clients consume the same versioned REST API, served by Django REST Framework.

> **Implementation status:** the implemented endpoints are health,
> authentication, organizations, workspaces, entities, statements, CSV
> imports and the line-item taxonomy ([below](#implemented-endpoints)). Every other
> resource in this document is designed but not yet built. The global behaviours (versioning, error envelope,
> request IDs, pagination, throttling, authentication defaults) are already
> configured in `backend/config/settings/base.py`.

## Versioning

- All client endpoints live under `/api/<version>/`. Today only `v1` exists (`URLPathVersioning`, `ALLOWED_VERSIONS = ["v1"]`), and requests to an unknown version such as `/api/v2/` return `404`.
- Within a version, changes are **additive only**: new endpoints, new optional request fields, and new response fields that clients must ignore if unknown.
- A breaking change requires a new version. `v2` gets its own URL module, and `v1` and `v2` are served side by side for a deprecation window of **at least 6 months**. During that window, `v1` responses carry `Deprecation` and `Sunset` headers, and the change is announced in `CHANGELOG.md`.
- A change in a calculation's methodology is not an API version change. It is reflected in the `engine_version` recorded on each analysis ([ADR-0003](../decisions/ADR-0003-deterministic-calculation-engine.md)).

## Resources and URLs

- Resource names are plural, kebab-case nouns, for example `/api/v1/workspaces/`.
- Identifiers in URLs and payloads are the resource's `public_id` (UUID). Sequential database keys are never exposed.
- **Every tenant resource is addressed under the workspace that owns it**, for example `/api/v1/workspaces/{public_id}/statements/`. The workspace is resolved and authorised once per request, and every queryset is filtered by it, so one resolver protects every endpoint ([ADR-0008](../decisions/ADR-0008-organizations-and-workspace-tenancy.md) §6). Children nest at most one more level: `/api/v1/workspaces/{public_id}/statements/{public_id}/line-items/`.
- Non-tenant resources (`auth/`, `me/`, `organizations/`) are top-level.
- Actions that do not map to CRUD use a verb sub-resource with `POST`, for example `POST /api/v1/workspaces/{public_id}/entities/{public_id}/analyses/` (body: the reporting period) to run an analysis. An analysis spans all statement types for one entity and period, so it hangs off the entity, not a single statement ([FOUNDATION_AUDIT FA-02](../architecture/FOUNDATION_AUDIT.md#fa-02--no-rule-for-assembling-one-fact-set-from-separate-statements-approved)).
- Trailing slashes are required, which is Django's default.

## Payloads

| Concern | Convention |
|---------|-----------|
| Format | JSON (`application/json`) only. File uploads (CSV, later PDF) use `multipart/form-data` on dedicated endpoints. |
| Field names | `snake_case`. |
| Money and other decimals | **Strings**, e.g. `"1250000.50"` (`COERCE_DECIMAL_TO_STRING = True`). Clients must not parse them as binary floats. |
| Currency | ISO 4217 alphabetic code, e.g. `"INR"`, sent alongside every monetary value or set of values. |
| Scale | Explicit, e.g. `"scale": "thousands"`. Values of the `Scale` enum: `units`, `thousands`, `lakhs`, `millions`, `crores`, `billions`. |
| Dates | ISO 8601 calendar dates: `"2025-12-31"`. |
| Timestamps | ISO 8601 in UTC with `Z`: `"2026-10-25T09:30:00Z"`. |
| Enumerations | Lowercase `snake_case` strings matching the domain codes (e.g. `"balance_sheet"`, `"gross_margin"`). |
| Missing values | `null`, never `0`. A missing financial figure is not zero. |
| Calculation warnings | Data inside a `200` response (e.g. an `issues` array with `code`, `severity`, `message`), never an HTTP error. |

## Errors

Every error response uses one envelope, produced by `api.exceptions.api_exception_handler` and by the JSON `404`/`500` handlers:

```json
{
  "error": {
    "code": "validation_error",
    "message": "The request is invalid.",
    "details": {"amount": ["A valid number is required."]},
    "request_id": "6f1c0e4b9a8d4f2e8c3b7a1d2e4f6a8b"
  }
}
```

- `code` is stable and machine-readable; clients branch on it.
- `message` is safe to show to users.
- `details` holds field-level errors for `validation_error` and is `null` otherwise.
- `request_id` matches the `X-Request-ID` response header.
- Exception text, stack traces and SQL never appear in a response.

| HTTP status | `code` | When |
|-------------|--------|------|
| 400 | `validation_error` | Input failed validation. |
| 400 | `parse_error` | Malformed JSON. |
| 401 | `not_authenticated`, `authentication_failed` | Missing or invalid credentials. The response carries `WWW-Authenticate: Session` ([ADR-0007](../decisions/ADR-0007-authentication-and-sessions.md)). |
| 403 | `permission_denied` | Authenticated, but not allowed (e.g. a viewer attempting a write). A CSRF failure is also `403`. |
| 404 | `not_found` | Unknown resource, or one the caller may not see. Existence is not revealed to callers without access. A non-member always gets `404` for a workspace and everything in it. |
| 405 | `method_not_allowed` | Wrong HTTP method. |
| 406 | `not_acceptable` | Unsupported `Accept` header. |
| 409 | `conflict` | The request would break an invariant, for example removing a workspace's last owner or an organization's last admin. Use cases raise `services.errors.ConflictError`, and the handler maps it with its safe message. |
| 413 | `payload_too_large` | An upload above its endpoint's limit. It is refused before anything is stored. |
| 415 | `unsupported_media_type` | Unsupported `Content-Type`. |
| 429 | `throttled` | Rate limit exceeded; the `Retry-After` header is set. |
| 500 | `server_error` | Unexpected failure. The error is logged with the request ID. |
| 503 | — | Only from the health endpoint, which returns its own body. |

## Pagination

List endpoints are paginated by default (`api.pagination.StandardPagination`):

- Query parameters are `?page=<n>&page_size=<m>`. The default page size is **50** and the maximum is **200**; larger requests are capped.
- Response shape:

```json
{
  "count": 123,
  "next": "https://finlume.example.org/api/v1/workspaces/?page=2",
  "previous": null,
  "results": []
}
```

Cursor pagination may be introduced for large, append-only collections such as transactions or audit events. If it is, it will be documented per endpoint.

## Filtering and ordering (designed)

- Filters are plain query parameters named after fields: `?statement_type=balance_sheet&period_end=2025-12-31`.
- Ranges use `__gte` and `__lte` suffixes: `?period_end__gte=2024-01-01`.
- Ordering uses `?ordering=period_end` or `?ordering=-created_at`, and only whitelisted fields can be used.
- Unknown filter parameters are rejected with `validation_error` rather than ignored.

## Idempotency

Endpoints that create imports or analysis runs accept an `Idempotency-Key` header, a client-generated UUID. Replaying the same key with the same body returns the original result instead of creating a duplicate; replaying it with a different body returns `409`. A key that is not a UUID is a `400`. Keys are scoped to the user and workspace. **Implemented** for CSV imports, where "the same body" means the same file for the same entity; analysis runs follow in step 5.

## Request IDs

Every response carries an `X-Request-ID` header. A caller-supplied `X-Request-ID` matching `[A-Za-z0-9._-]{1,64}` is propagated. Any other value is replaced with a generated 32-character hex ID. The ID appears in every log line and in error bodies. Include it in bug reports.

## Authentication and authorisation

- Default authentication: `apps.accounts.api.authentication.SessionAuthentication`, DRF's session authentication plus the `Session` challenge. Users sign in with their email address, and sessions expire after 8 hours of inactivity (`FINLUME_SESSION_AGE_SECONDS`), renewed by every request ([ADR-0007](../decisions/ADR-0007-authentication-and-sessions.md)).
- Default permission: `IsAuthenticated`. Every endpoint requires a logged-in user unless it explicitly opts out; today only the health endpoint does.
- **Web client:** Django session cookie plus CSRF. Unsafe methods send the token in the `X-CSRFToken` header. The SPA is served from the same origin as the API, through a reverse proxy in production and the Vite dev proxy locally, so CORS is not needed ([ADR-0006](../decisions/ADR-0006-client-stack.md)).
- **Mobile client:** token-based authentication, to be decided by an ADR when the mobile phase begins.
- Object access is always checked against workspace membership, through the shared resolver and workspace-scoped querysets. Authentication alone never grants access to data, and neither does organization membership or the organization admin role ([ADR-0008](../decisions/ADR-0008-organizations-and-workspace-tenancy.md)).

## Rate limiting

| Scope | Default | Setting |
|-------|---------|---------|
| Anonymous | `60/minute` | `FINLUME_THROTTLE_ANON` |
| Authenticated user | `1000/hour` | `FINLUME_THROTTLE_USER` |
| Sign-in, per client IP | `5/minute` | `FINLUME_THROTTLE_LOGIN_IP` |
| Sign-in, per submitted email (hashed in the cache key) | `5/minute` | `FINLUME_THROTTLE_LOGIN_EMAIL` |
| Adding organization members by email, per user | `30/hour` | `FINLUME_THROTTLE_ORGANIZATION_MEMBER_ADD` |

Throttle state uses Django's default cache, which is per process. A multi-process deployment needs a shared cache before limits are exact (see [SCALABILITY_AND_DEPLOYMENT](../architecture/SCALABILITY_AND_DEPLOYMENT.md)). The health endpoint is not throttled.

## Schema and documentation

An OpenAPI 3 schema generated with drf-spectacular is planned for Phase 1, and typed web and mobile API clients will be generated from it. It is **not available yet**. Until then, this document is the contract.

## Implemented endpoints

### Authentication ([ADR-0007](../decisions/ADR-0007-authentication-and-sessions.md))

| Endpoint | Access | Success | Notes |
|---|---|---|---|
| `GET auth/csrf/` | Public | `204`, sets the `csrftoken` cookie | Call once before the first write. The client sends the cookie value in `X-CSRFToken` |
| `POST auth/register/` `{"email", "password"}` | Public, CSRF-checked | `201`, the current user; signed in | Creates the personal workspace in the same transaction. A duplicate email (any case) → `409 conflict`; a weak password → `400` with `details.password` |
| `POST auth/login/` `{"email", "password"}` | Public, CSRF-checked, throttled | `200`, the current user | Email matched regardless of case. Any failure (wrong password, unknown email, inactive account) → the same `401 authentication_failed`. Every attempt is audited |
| `POST auth/logout/` | Signed in | `204` | Ends the session server-side |
| `GET me/` | Signed in | `200`, the current user | |

Current user: `{"id": "<uuid>", "email": "…", "personal_workspace_id": "<uuid>"}`.

### Organizations ([ADR-0008](../decisions/ADR-0008-organizations-and-workspace-tenancy.md))

Organization membership never grants access to the organization's workspaces, not even for admins. A caller who is not a member gets `404`, so the organization's existence is not revealed.

| Endpoint | Access | Success | Notes |
|---|---|---|---|
| `GET organizations/` | Signed in | `200`, a page of the caller's organizations | Each with `my_role` |
| `POST organizations/` `{"name"}` | Signed in | `201`, the organization | The creator becomes its admin |
| `GET organizations/{id}/` | Member | `200`, the organization | |
| `PATCH organizations/{id}/` `{"name"}` | Admin | `200`, the organization | |
| `GET organizations/{id}/members/` | Member | `200`, a page of members | |
| `POST organizations/{id}/members/` `{"email", "role"}` | Admin, throttled | `201`, the member | Adds an existing, active account. Unknown or inactive email, or already a member → `409 conflict` |
| `PATCH organizations/{id}/members/{user_id}/` `{"role"}` | Admin | `200`, the member | Demoting the last admin → `409` |
| `DELETE organizations/{id}/members/{user_id}/` | Admin, or the member themselves (leave) | `204` | Also removes their memberships in the organization's workspaces. The last admin, or the last owner of one of its workspaces → `409` |

Organization: `{"id", "name", "my_role": "admin" | "member", "created_at"}`. Member: `{"user_id", "email", "role", "joined_at"}`.

### Workspaces ([ADR-0008](../decisions/ADR-0008-organizations-and-workspace-tenancy.md))

Access comes only from workspace membership. A caller who is not a member gets `404`, including an admin of the workspace's organization. Every later tenant resource is nested under `workspaces/{id}/` and inherits the same check.

| Endpoint | Access | Success | Notes |
|---|---|---|---|
| `GET workspaces/` | Signed in | `200`, a page of the caller's workspaces | Personal and organization workspaces, each with `my_role` |
| `POST workspaces/` `{"organization_id", "name"}` | Member of that organization | `201`, the workspace | Always an organization workspace; the creator becomes its owner. Not a member of the organization → `404` |
| `GET workspaces/{id}/` | Viewer | `200`, the workspace | |
| `PATCH workspaces/{id}/` `{"name"}` | Owner | `200`, the workspace | |
| `GET workspaces/{id}/members/` | Viewer | `200`, a page of members | |
| `POST workspaces/{id}/members/` `{"user_id", "role"}` | Owner | `201`, the member | The user must be an active member of the workspace's organization. Otherwise, already a member, or a personal workspace → `409 conflict` |
| `PATCH workspaces/{id}/members/{user_id}/` `{"role"}` | Owner | `200`, the member | Demoting the last owner → `409`. Transferring ownership is setting another member's role to `owner` |
| `DELETE workspaces/{id}/members/{user_id}/` | Owner, or the member themselves (leave) | `204` | The last owner → `409` |

Workspace: `{"id", "name", "kind": "personal" | "organization", "organization_id", "my_role": "owner" | "editor" | "viewer", "created_at"}`; `organization_id` is `null` for a personal workspace. Member: `{"user_id", "email", "role", "joined_at"}`.

### Entities and statements (MVP step 3)

Under `workspaces/{ws}/`. Viewers read; editors and owners write. An entity or statement ID from another workspace is not found (`404`).

| Endpoint | Access | Success | Notes |
|---|---|---|---|
| `GET entities/` | Viewer | `200`, a page of entities | Ordered by name |
| `POST entities/` `{"name", "entity_type", "default_currency"?, "fiscal_year_end_month"?}` | Editor | `201`, the entity | `entity_type`: `business`, `individual` or `listed_company`. A name already used in the workspace → `409` |
| `GET entities/{id}/` | Viewer | `200`, the entity | |
| `GET entities/{id}/statements/` | Viewer | `200`, a page of statements | Every version, latest period first |
| `POST entities/{id}/statements/` | Editor | `201`, the draft with its rows | Creates version 1 as a `draft`, with a manual-entry source. A statement of that type already existing for the period → `409` (edit its draft, or restate it) |
| `GET statements/{id}/` | Viewer | `200`, the statement with its rows and facts | `facts` is empty for a draft |
| `PATCH statements/{id}/` | Editor | `200`, the statement with its rows and facts | Drafts only, otherwise `409`. Sending `line_items` replaces every row. Changing `statement_type` or `reported_scale` requires sending `line_items` again. A restatement draft keeps its statement type and period (`409`) |
| `POST statements/{id}/validate/` | Editor | `200`, the statement with its rows, facts and `issues` | Draft → `validated`. Each mapped row with an amount becomes a `confirmed` fact in base units. For a restatement, the version it restates becomes `superseded` in the same transaction. Consistency warnings (`unexpected_sign`, `balance_sheet_imbalance`, `subtotal_mismatch`) are returned in `issues` and never block. Not a draft, or no mapped figure at all → `409` |
| `POST statements/{id}/restatements/` `{"reason", "line_items"?}` | Editor | `201`, the new draft with its rows | Only the `validated` version, otherwise `409`. Creates version *n + 1* as a draft that restates it. Without `line_items`, the rows of version *n* are copied. Version *n*, its facts and the analyses that used them stay unchanged until the draft is validated. A restatement already in progress → `409` |

Statement body: `{"statement_type", "period_start", "period_end", "period_type", "currency", "reported_scale", "line_items": [{"label", "line_item_code"?, "amount"?, "source_reference"?}]}`. Rows are numbered in the order sent.

Input rules, each answered with a field-level `400 validation_error` (`details.line_items.<index>.<field>` for a row):

- `amount` is a decimal **string** (`"1250.50"`, `"-3.25"`, `"1e3"`) or `null` for a blank cell. JSON numbers are refused, so a figure never passes through a binary float. At most 6 decimal places and 64 characters. Its magnitude must be below 10²⁴ both as entered and once scaled to units (FOUNDATION_AUDIT FA-15).
- `line_item_code` is a taxonomy code, or blank for an unmapped row. It must belong to the statement's type, and appear at most once per statement.
- `currency` is three uppercase letters; `period_end` is not before `period_start`; at most 500 rows.

Statement: `{"id", "entity_id", "statement_type", "period_start", "period_end", "period_type", "currency", "reported_scale", "status", "version", "supersedes_id", "restatement_reason", "created_at", "updated_at"}`, plus `line_items` on a single statement. Row: `{"id", "row_number", "label", "line_item_code", "amount", "raw_value", "source_reference"}`. `amount` is the figure as entered, in the reported scale, with 6 decimal places; `raw_value` is the exact text sent. Fact: `{"line_item", "value", "row_id", "review_status"}`, where `value` is in base units and `row_id` is the row it came from. Issue: `{"code", "severity", "message", "line_items"}`.

Statuses change only by validating a draft, so they always match the restatement chain: one `validated` version per statement and period, earlier versions `superseded`, and at most one restatement `draft` in progress.

### CSV imports (MVP step 4)

`POST workspaces/{ws}/entities/{id}/imports/`. Editor. `multipart/form-data` only (`415` otherwise), with the statement fields (`statement_type`, `period_start`, `period_end`, `period_type`, `currency`, `reported_scale`) and the CSV as `file`. Optional `Idempotency-Key`.

The upload becomes a **draft** statement whose rows carry a proposed code each. The user reviews and corrects them with `PATCH statements/{id}/`, and `POST statements/{id}/validate/` creates the facts. Nothing is a fact before that review (FR-014).

The file (one statement):

- The first non-empty line is the header: `label` and `amount`, and optionally `code`, in any order and any case. Any other column is refused.
- `amount` is blank for an empty cell (unknown, never zero), or a number in the reported scale: `1234.56`, `-1234.56`, `(1,234.56)` for a negative, and comma grouping such as `1,23,456.78`. The decimal separator is a point. The value is read exactly, never through a binary float, and the cell text is kept as the row's `raw_value`. Signs are kept: a cost written in parentheses arrives negative and is flagged by validation, not flipped.
- `code` is optional. Without it, a code is proposed only when the label is exactly a line item's name, ignoring case, spaces and underscores (`Net income`, `total_assets`), and only for the statement's own type. There is no fuzzy matching.
- UTF-8 text, with or without a byte-order mark. The file's content decides this, not the client's content type.

Limits and refusals:

| Case | Answer |
|---|---|
| File above `FINLUME_MAX_UPLOAD_BYTES` (1 MiB) | `413 payload_too_large`. A request clearly above it is refused from its `Content-Length`, before the body is read. The upload is kept in memory, never in a temporary file. |
| More rows than `FINLUME_MAX_IMPORT_ROWS` (500), a bad header, not UTF-8 text, or broken quoting | `400`, `details.file` |
| Row problems: not a number, more than 6 decimal places, too large as entered or once scaled, an unknown code, a code from another statement type or used twice, a missing label, the wrong number of columns | `400`, every problem at once in `details.rows.<line>.<column>`, keyed by the file's line number |
| A statement of that type already existing for the period | `409` |

On any refusal nothing is stored: neither the file nor a row. A row's `source_reference` is its file line (`line 7`).

Response: `201`, the draft (as `GET statements/{id}/`), plus `document` (`{"id", "kind", "filename", "size_bytes", "sha256", "created_at"}`) and `warnings`. Uploading a file already uploaded to the workspace succeeds with a `duplicate_file` warning naming the earlier document. The file is stored privately under a random key and has no URL.

### `GET line-items/` (MVP step 3a)

Signed in. The canonical line items, as one complete page: `{"code", "statement_type", "label", "definition", "sign": "non_negative" | "non_positive" | "signed"}`. `definition` is the help text for entry forms ([calculation conventions §4](../data/FINANCIAL_CALCULATION_CONVENTIONS.md#4-line-item-taxonomy-implemented)).

### `GET /api/v1/health/`

Public, unthrottled readiness probe. It runs outside the request transaction and returns `Cache-Control: no-store`.

| Status | Body |
|--------|------|
| 200 | `{"status": "ok", "checks": {"database": "ok"}}` |
| 503 | `{"status": "unavailable", "checks": {"database": "unavailable"}}` |

The response never includes versions, host names or error text.
