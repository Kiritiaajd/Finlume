# API conventions

The Finlume web and mobile clients consume the same versioned REST API, served by Django REST Framework.

> **Implementation status:** the implemented endpoints are health,
> authentication and workspaces ([below](#implemented-endpoints)). Every other resource in
> this document is designed but not yet built. The global behaviours (versioning, error envelope,
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
- Actions that do not map to CRUD use a verb sub-resource with `POST`, for example `POST /api/v1/workspaces/{public_id}/entities/{public_id}/analyses/` (body: the reporting period) to run an analysis. An analysis spans all statement types for one entity and period, so it hangs off the entity, not a single statement ([FOUNDATION_AUDIT FA-02](../architecture/FOUNDATION_AUDIT.md#fa-02--no-rule-for-assembling-one-fact-set-from-separate-statements-needs-approval)).
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

## Idempotency (designed)

Endpoints that create imports or analysis runs will accept an `Idempotency-Key` header, a client-generated UUID. Replaying the same key with the same body returns the original result instead of creating a duplicate; replaying it with a different body returns `409`.

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

### Workspaces ([ADR-0008](../decisions/ADR-0008-organizations-and-workspace-tenancy.md))

All need a signed-in user. Under `workspaces/{id}/`, a non-member gets `404` and a member
without the required role gets `403`.

| Endpoint | Minimum role | Success | Notes |
|---|---|---|---|
| `GET workspaces/` | — | `200`, paginated | Only the caller's workspaces, with `my_role` |
| `POST workspaces/` `{"organization_id", "name"}` | Member of that organization | `201`; creator is owner | Personal workspaces are created only at registration |
| `GET workspaces/{id}/` | viewer | `200` | |
| `PATCH workspaces/{id}/` `{"name"}` | owner | `200` | |
| `GET workspaces/{id}/members/` | viewer | `200`, paginated | |
| `POST workspaces/{id}/members/` `{"user_id", "role"}` | owner | `201` | The user must be an active member of the organization; personal workspaces take no members (`409`) |
| `PATCH workspaces/{id}/members/{user_id}/` `{"role"}` | owner | `200` | Demoting the last owner → `409` |
| `DELETE workspaces/{id}/members/{user_id}/` | viewer for yourself (leave), owner for others | `204` | Removing the last owner → `409` |

Workspace: `{"id", "name", "kind": "personal" | "organization", "organization_id", "my_role", "created_at"}`.
Member: `{"user_id", "email", "role", "joined_at"}`.

Ownership recovery, for workspaces whose owners are all deactivated, has no endpoint by
design. It is the operator command `manage.py recover_workspace_owner`.

### `GET /api/v1/health/`

Public, unthrottled readiness probe. It runs outside the request transaction and returns `Cache-Control: no-store`.

| Status | Body |
|--------|------|
| 200 | `{"status": "ok", "checks": {"database": "ok"}}` |
| 503 | `{"status": "unavailable", "checks": {"database": "unavailable"}}` |

The response never includes versions, host names or error text.
