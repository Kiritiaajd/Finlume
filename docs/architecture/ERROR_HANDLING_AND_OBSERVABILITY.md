# Error Handling and Observability

This document describes how Finlume reports errors to clients, how failures are
logged and correlated, and which observability capabilities will be added
later. Statements marked **Implemented** describe code in `backend/apps/core/`
and `backend/config/settings/base.py`.

Related: [API_CONVENTIONS.md](../api/API_CONVENTIONS.md), [SECURITY_AND_PRIVACY.md](SECURITY_AND_PRIVACY.md).

## 1. Two kinds of "problem"

Finlume separates **API errors** from **domain issues**:

| | API error | Domain issue |
|---|---|---|
| Meaning | The request could not be processed (invalid input, not authenticated, not found, server failure) | The request succeeded, but the financial data deserves attention (missing input, zero denominator, balance sheet does not balance) |
| Transport | Non-2xx HTTP status with the error envelope (§2) | **Data inside a successful (2xx) response**, e.g. on a metric result or an analysis run |
| Source | DRF / Django / `api.exceptions` | `domain.validation.Issue` with a stable `IssueCode` and a `Severity` |
| Example | `400 validation_error`: `amount` is not a number | `200` with gross margin `null` plus issue `missing_input` for `gross_profit` |

A ratio that cannot be computed is a valid, explainable result, not an HTTP
failure. The domain never raises exceptions for financial edge cases. It
returns `MetricResult(value=None, issues=(…))`, and the API serialises that.
Domain exceptions (`TypeError`/`ValueError` for floats, NaN or malformed
currency codes) indicate programming or validation bugs. Input must be
validated at the API boundary before it reaches the domain.

Domain issue codes are implemented in `domain/validation/issues.py`:

| `IssueCode` | Raised when |
|---|---|
| `missing_input` | A metric's numerator or denominator line item is absent (never treated as zero) |
| `zero_denominator` | The denominator is exactly zero; the metric value is `null` |
| `negative_denominator` | The ratio was computed, but its denominator is negative (e.g. return on negative equity) |
| `unexpected_sign` | A value violates Finlume's sign convention (e.g. negative revenue, positive capital expenditure) |
| `balance_sheet_imbalance` | Total assets ≠ total liabilities + total equity beyond 0.1 % tolerance |
| `subtotal_mismatch` | Gross profit ≠ revenue − cost of revenue beyond 0.1 % tolerance |

Severities are `info`, `warning` (the result is usable but should be reviewed)
and `error` (the input cannot be analysed until corrected).

## 2. API error envelope (Implemented)

Every API error uses one shape (`api/exceptions.py`):

```json
{
  "error": {
    "code": "validation_error",
    "message": "The request is invalid.",
    "details": {"amount": ["A valid number is required."]},
    "request_id": "81713313140d4c9f8c53daa851e91668"
  }
}
```

- **`code`** is a stable, machine-readable string. Clients branch on `code`, never on `message`.
- **`message`** is safe to show to users. It never contains exception text, SQL or stack traces.
- **`details`** holds field-level errors for `validation_error`, and `null` otherwise.
- **`request_id`** matches the `X-Request-ID` response header and the server logs.

### Codes produced today

| HTTP | `code` | Produced by |
|---|---|---|
| 400 | `validation_error` | Any DRF `ValidationError` (field errors in `details`) |
| 400 | `parse_error` | Malformed JSON body |
| 401 / 403 | `not_authenticated`, `authentication_failed` | DRF authentication |
| 403 | `permission_denied` | DRF `PermissionDenied` and Django `PermissionDenied` (mapped) |
| 404 | `not_found` | DRF `NotFound`, Django `Http404` (mapped), and unknown URLs (`handler404`) |
| 405 | `method_not_allowed` | DRF |
| 406 | `not_acceptable` | DRF content negotiation |
| 415 | `unsupported_media_type` | DRF (only JSON is accepted) |
| 429 | `throttled` | DRF throttles |
| 500 | `server_error` | Any unhandled exception (`handler500`) |

DRF returns 403 rather than 401 for unauthenticated requests under
`SessionAuthentication`, because that scheme sends no `WWW-Authenticate`
header. Clients should treat `code` as authoritative.

### How unexpected exceptions propagate

1. `api_exception_handler` wraps DRF's handler. For known API exceptions it rewrites the body into the envelope.
2. For any other exception it returns `None`. DRF re-raises it.
3. Django then:
   - rolls back the request transaction (`ATOMIC_REQUESTS = True`);
   - logs the exception through the `django.request` logger, with the request ID attached;
   - fires `got_request_exception`, which future error-tracking integrations hook into;
   - answers through `apps.core.views.server_error`: `500 {"error": {"code": "server_error", "message": "An unexpected error occurred.", …}}`.

With `DEBUG = True` (development only), Django shows its technical 404 and 500
pages instead of the JSON handlers. Tests run with `DEBUG = False` and assert
the JSON behaviour.

## 3. Request IDs (Implemented)

`apps.core.middleware.RequestIDMiddleware` is the first middleware:

- If the request carries `X-Request-ID` matching `[A-Za-z0-9._-]{1,64}`, the middleware reuses it, so an ID from a reverse proxy or the client flows through. Otherwise it generates a 32-character hex UUID4.
- It stores the ID in a `ContextVar` (`apps/core/request_context.py`), which logging and error handlers can read anywhere in the request.
- It returns the ID in the `X-Request-ID` response header on every response, including errors.

Future background jobs must carry the originating request ID in their task
metadata and set the same context variable while running.

## 4. Logging (Implemented)

Configured in `LOGGING` in `config/settings/base.py`:

- **Output:** a single console (stderr) handler, as a twelve-factor app would. The process manager or container runtime collects the stream.
- **Format:** `%(asctime)s %(levelname)s %(name)s [request_id=%(request_id)s] %(message)s`. `apps.core.logging.RequestIDFilter` adds `request_id` to every record (`-` outside a request). Django logs 4xx responses (`django.request`) after the middleware has returned, so the filter takes the ID from the request attached to the record, where the middleware also stores it (`request.META["FINLUME_REQUEST_ID"]`).
- **Level:** `FINLUME_LOG_LEVEL` (default `INFO`).
- **SQL logging:** `django.db.backends` is pinned to `WARNING`, because queries can contain financial values.
- **Content rules:** never log financial values, document content, credentials, tokens or personal data. Log `public_id`s, counts, durations and codes ([SECURITY_AND_PRIVACY.md §9](SECURITY_AND_PRIVACY.md#9-logging-rules)).

## 5. Health endpoint (Implemented)

`GET /api/v1/health/`, served by `apps.core.views.HealthView`:

| Property | Value |
|---|---|
| Purpose | Readiness: is the app running, and can it reach its database (`SELECT 1`)? |
| Authentication | None (`AllowAny`, no authentication classes). It must work for load balancers. |
| Throttling | None, so frequent probes are never rejected |
| Transaction | Excluded from `ATOMIC_REQUESTS` (`transaction.non_atomic_requests`), so a database outage yields 503 rather than an unhandled 500 when Django opens the transaction |
| Healthy | `200 {"status": "ok", "checks": {"database": "ok"}}` |
| Database unreachable | `503 {"status": "unavailable", "checks": {"database": "unavailable"}}`; the cause is logged server-side only |
| Caching | `Cache-Control: no-store` |
| Disclosure | No versions, host names or error text |

A separate liveness endpoint (process up, no dependency checks) can be added
when an orchestrator needs one. Future checks (storage writable, queue
reachable) will be added to `checks` as their components arrive.

## 6. Planned observability

| Capability | Plan | When |
|---|---|---|
| Structured JSON logs | Optional JSON formatter selected by an environment variable, with the same fields (`request_id`, logger, level) plus user `public_id` and workspace `public_id` where known | Before the first production deployment |
| Audit events | `AuditEvent` rows for security-relevant and data-changing actions, without financial values. Audit events are a data feature, not logging. | Phase 1 |
| Metrics | Request rate, latency and error rate; analysis run counts and durations; ingestion queue depth. Exposed in Prometheus format behind an authenticated or internal-only endpoint, or via OpenTelemetry metrics | Phase 2 |
| Tracing | OpenTelemetry instrumentation for Django, psycopg and Celery, exporting OTLP to an operator-chosen backend. Disabled unless configured. | Phase 2 (when background jobs arrive) |
| Error tracking | Opt-in integration (e.g. Sentry or a self-hosted compatible service). Request bodies, cookies, headers and personal data scrubbed before sending. Disabled by default, consistent with privacy by default. | When needed; must be operator opt-in |
| Job observability | Celery task IDs, retries and failure reasons, correlated with request IDs | Phase 2 |

Every observability integration must:

1. be off by default and configured through environment variables;
2. never export financial values or document content;
3. be documented in [SCALABILITY_AND_DEPLOYMENT.md](SCALABILITY_AND_DEPLOYMENT.md) and `.env.example`.
