# Security and Privacy

Finlume handles financial records, source documents and identity data. This
document defines the security and privacy rules every module must follow and
records which controls exist in code today.

Status labels used throughout:

- **Implemented**: present in the repository now and covered by tests or `manage.py check`.
- **Planned (Phase N)**: designed, to be built in the named phase (see [PRODUCT_SCOPE.md](../product/PRODUCT_SCOPE.md)).
- **Open**: a decision is still required.

Related: [THREAT_MODEL.md](THREAT_MODEL.md), [ADR-0005](../decisions/ADR-0005-private-document-storage.md),
[DATA_LIFECYCLE_AND_RETENTION.md](../data/DATA_LIFECYCLE_AND_RETENTION.md), [SECURITY.md](../../SECURITY.md).

---

## 1. Principles

1. **Secure by default.** Every API endpoint requires authentication unless it explicitly opts out. Unsafe production configuration stops the process at startup.
2. **Least privilege.** Users see only workspaces they are members of, with the role they were granted.
3. **Data minimisation.** Collect only what an analysis needs; never log financial values or personal data.
4. **Private by default.** No telemetry, no third-party calls, and no AI processing unless an operator explicitly enables them.
5. **Verifiable correctness.** Calculations are deterministic and versioned, so a tampered or wrong result can be detected by recomputation ([ADR-0003](../decisions/ADR-0003-deterministic-calculation-engine.md)).

## 2. Authentication

| Aspect | Decision | Status |
|---|---|---|
| Identity model | Custom user `apps.accounts.User` (`AUTH_USER_MODEL = "accounts.User"`), created before the first migration. Email is unique case-insensitively (`accounts_user_email_ci_unique`). | Implemented |
| Password policy | Django validators: user-attribute similarity, minimum length **12**, common-password list, not entirely numeric. | Implemented |
| Password hashing | Django default (PBKDF2). Argon2 can be added later without a migration. Test settings use MD5 for speed **only in tests**. | Implemented |
| Web client authentication | Django session cookie + CSRF token. The SPA is served from the same origin as the API (a reverse proxy in production, the Vite dev proxy locally), so no CORS is configured. | Implemented (DRF `SessionAuthentication`); login/logout endpoints Planned (Phase 1) |
| Mobile client authentication | Token-based scheme (expiring, revocable tokens or OAuth2/OIDC) to be chosen in a future ADR before mobile work starts. | **Open** |
| Login brute-force protection | DRF throttles apply to API endpoints (`anon` 60/minute, `user` 1000/hour by default). Dedicated login throttling and lockout/backoff are added with the login endpoint. | Partly implemented; login-specific controls Planned (Phase 1) |
| Multi-factor authentication | TOTP-based MFA, at least for admin users. | Planned (after Phase 1) |
| Admin site | Django Admin for internal administration, at a configurable path (`FINLUME_ADMIN_URL_PATH`, default `admin/`). Changing the path reduces automated noise but is not a security control. | Implemented |

## 3. Authorization

### 3.1 Boundaries

```text
Internet ──▶ Reverse proxy (TLS) ──▶ Django/DRF ──▶ Application layer ──▶ Domain
                                        │                 │
                              authentication      workspace authorization
                              (who are you?)      (may you touch this object?)
```

- **Authentication boundary** (presentation layer): DRF's default permission is `IsAuthenticated`. Only the health endpoint opts out (`AllowAny`, no authentication classes). **Implemented.**
- **Tenancy boundary**: the **workspace** (kind `personal` or `business`). Every user-owned financial record belongs to exactly one workspace. **Planned (Phase 1).**
- **Role boundary**: membership roles `owner`, `editor` and `viewer`. **Planned (Phase 1).**

### 3.2 Workspace-scoped object authorization (Phase 1 rules)

These rules apply to every module that stores user data:

1. **Scope every query by workspace.** Querysets start from the workspaces the requesting user belongs to. Never fetch by ID and then check ownership as an afterthought.
2. **Return 404, not 403, for objects outside the user's workspaces,** so the API does not reveal that an object exists.
3. **Enforce role permissions in the application layer** (use cases), not only in views. Background jobs and the admin then follow the same rules.
4. **Expose `public_id` UUIDs only.** Sequential primary keys never leave the server. This is already implemented for `User.public_id`.
5. **Check write access separately from read access.** Viewers read; editors create and modify data; owners also manage membership and deletion.
6. **Test every endpoint's authorization**, including a cross-workspace access attempt (see [TESTING_STRATEGY.md](TESTING_STRATEGY.md)).

| Role | Read | Create/edit statements, run analyses | Manage members, delete workspace |
|---|---|---|---|
| viewer | ✓ | | |
| editor | ✓ | ✓ | |
| owner | ✓ | ✓ | ✓ |

## 4. Secrets management

| Rule | Status |
|---|---|
| No secrets in the repository. `.env`, `.env.*` (except `.env.example`), key files and `secrets/` are git-ignored. | Implemented |
| `.env.example` contains placeholders only. | Implemented |
| Configuration is read from environment variables through `config/env.py`. A malformed boolean or integer raises `ImproperlyConfigured` instead of falling back silently. | Implemented |
| The optional repository-root `.env` is loaded with `setdefault`, so real environment variables always win. | Implemented |
| Production refuses to start without `DJANGO_SECRET_KEY` (minimum 50 characters), without `DJANGO_ALLOWED_HOSTS`, without PostgreSQL credentials, or with a database engine other than PostgreSQL. These cases are tested in `tests/config/test_settings.py`. | Implemented |
| Development without `DJANGO_SECRET_KEY` generates a random key per process, so no development key is ever committed. | Implemented |
| Production secrets come from the platform's secret store (environment injection, Docker/Kubernetes secrets, systemd credentials). Rotating `DJANGO_SECRET_KEY` invalidates sessions; plan rotations. | Operator responsibility |
| Future provider API keys (market data, AI) are server-side only, per instance, never sent to clients and never stored in the database in plain text. | Planned (Phases 3 and 5) |

## 5. Transport and HTTP security settings

These are implemented in `backend/config/settings/`.

| Setting | Value | Where |
|---|---|---|
| `DEBUG` | `False` (only `True` in `development.py`) | base / production |
| `SECURE_CONTENT_TYPE_NOSNIFF` | `True` | base |
| `SECURE_REFERRER_POLICY` | `same-origin` | base |
| `SECURE_CROSS_ORIGIN_OPENER_POLICY` | `same-origin` | base |
| `X_FRAME_OPTIONS` | `DENY` | base |
| `SESSION_COOKIE_HTTPONLY` | `True` | base |
| `SESSION_COOKIE_SAMESITE` / `CSRF_COOKIE_SAMESITE` | `Lax` | base |
| `CSRF_COOKIE_HTTPONLY` | `False` (Django default) so the same-origin SPA can read the token and send `X-CSRFToken` | default |
| `SECURE_SSL_REDIRECT` | `True` unless `FINLUME_SECURE_SSL_REDIRECT=false` | production |
| `SECURE_PROXY_SSL_HEADER` | set only when `FINLUME_TRUST_PROXY_SSL_HEADER=true` (only behind a TLS-terminating proxy that overwrites `X-Forwarded-Proto`) | production |
| `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` | `True` | production |
| `SECURE_HSTS_SECONDS` | `FINLUME_HSTS_SECONDS`, default `0` | production |
| `CSRF_TRUSTED_ORIGINS` | `DJANGO_CSRF_TRUSTED_ORIGINS` | base / production |
| `DATA_UPLOAD_MAX_MEMORY_SIZE`, `FILE_UPLOAD_MAX_MEMORY_SIZE` | `FINLUME_MAX_REQUEST_BYTES`, default 5 MiB. Caps request bodies and non-file form fields only. Uploaded files are **not** capped by Django; this value is just the threshold for spooling them to a temporary file. | base |
| PostgreSQL `sslmode` | `POSTGRES_SSLMODE`, default `prefer`. Use `require` or `verify-full` when the database is on another host. | base |
| DRF parsers / renderers | JSON only. The browsable API renderer is added in development only. | base / development |
| Monetary values in JSON | Decimals are serialised as strings (`COERCE_DECIMAL_TO_STRING`) | base |

`manage.py check --deploy` with production settings currently reports only
`security.W004` (HSTS not set). This is deliberate. HSTS is hard to undo, so
the operator enables it with `FINLUME_HSTS_SECONDS` once HTTPS works for every
host, starting with a small value.

A Content Security Policy belongs with the web client. It will be set at the
reverse proxy or with Django's CSP support when the frontend is introduced.
**Status: Planned (Phase 1).**

## 6. Private document storage

Implemented in `backend/infrastructure/storage/`; see [ADR-0005](../decisions/ADR-0005-private-document-storage.md).

- **No public URLs.** Both the `default` and `private_documents` storages use `PrivateFileSystemStorage`. Its `url()` method raises `PublicURLNotAllowedError`. Because `default` is private too, a `FileField` that forgets to name a storage still cannot become public.
- **Not served by anything.** Django has no `MEDIA_URL` route, and the web server must not serve the storage directory. Files reach users only through an authenticated, workspace-authorised API view that streams them (Planned, Phase 2).
- **Location check.** `PRIVATE_STORAGE_ROOT` (`FINLUME_PRIVATE_STORAGE_ROOT`, default `backend/var/private`) is checked by the system check `finlume.E001`, which fails `manage.py check` if the private root is inside `STATIC_ROOT`, `STATICFILES_DIRS` or `MEDIA_ROOT`.
- **Owner-only permissions.** Files are written with mode `0o600` and directories with `0o700` on POSIX systems. Windows ignores these modes, so rely on directory ACLs there.
- **Object storage later.** An object-storage backend (private bucket, server-side encryption, short-lived signed URLs issued only after authorization) can replace the filesystem class through `STORAGES` without changing callers. **Planned.**

## 7. Upload and import handling rules

CSV upload is part of the Phase 1 MVP; PDF and annual reports arrive in Phase 2.
These rules are binding for those implementations.

| Rule | Applies to | Phase |
|---|---|---|
| Enforce size limits at the reverse proxy and in each upload endpoint (check the file's size before reading or storing it; `FINLUME_MAX_REQUEST_BYTES` does not cover files), plus per-type limits on row count and page count. Spooled temporary files go to a private temp directory (`FILE_UPLOAD_TEMP_DIR`) that is cleaned up. | CSV, PDF | 1 / 2 |
| Identify file type by content (magic bytes and a parser attempt), not by extension or client `Content-Type`. Reject anything unexpected. | CSV, PDF | 1 / 2 |
| Generate storage names server-side (random); never use the client file name as a path. Keep the original name only as escaped metadata. | All uploads | 1 / 2 |
| Store a SHA-256 hash of every source file for provenance and duplicate detection. | All uploads | 1 / 2 |
| Parse CSV with an explicit encoding (UTF-8, with a BOM tolerated), a strict schema and an explicit decimal format. Values parse straight to `Decimal`; floats are never an intermediate step. | CSV | 1 |
| **CSV formula injection.** On any CSV or Excel export, prefix cells that start with `=`, `+`, `-`, `@`, tab or carriage return with `'` so spreadsheet applications do not run them. | Exports | 1 |
| **Decompression and archive bombs.** Do not accept ZIP or compressed uploads initially. If XLSX is added later, cap the uncompressed size, the number of archive entries and the compression ratio before parsing. | XLSX / archives | Later |
| **PDF parser isolation.** Parse PDFs in a background worker (Celery), never in the web request. Use time, memory and page limits and a pure-Python parser where possible, with no network access from the worker. Treat every extracted value as untrusted until reviewed. | PDF | 2 |
| Uploaded content is never executed, rendered as HTML or passed to a shell. | All | 1+ |
| Malware scanning (e.g. ClamAV) is optional, for operators who accept third-party uploads. | All | **Open** |

## 8. Data minimisation and privacy by default

- **No telemetry.** Finlume sends no usage data anywhere. **Implemented** (nothing in the codebase phones home). Any future product analytics must be opt-in, self-hostable and free of financial values.
- **AI is off by default.** Phase 3 AI explanations are optional and provider-pluggable, including a local-model option so data stays on the operator's infrastructure. AI receives only the stored, calculated results it explains, never performs arithmetic, and cites the metric results it uses. Sending data to an external AI provider requires an explicit operator setting and must be disclosed to users.
- **No external market-data or bank calls** unless an operator configures a provider (Phase 5 and later). Bank integrations are out of scope for now.
- **Collect what analysis needs.** User profiles hold username, email and password hash. No national ID numbers, tax IDs or bank credentials.
- **Retention and deletion** are defined in [DATA_LIFECYCLE_AND_RETENTION.md](../data/DATA_LIFECYCLE_AND_RETENTION.md). The concrete retention periods are **Open**.

## 9. Logging rules

| Rule | Status |
|---|---|
| Never log financial values, uploaded content, passwords, tokens, session IDs or full request bodies. Log identifiers (`public_id`) and counts instead. | Binding rule; enforced in review |
| SQL query logging (`django.db.backends`) is pinned at `WARNING`, because queries can contain financial values. | Implemented |
| Every log line carries the request ID (`[request_id=…]`) for correlation without logging personal data. | Implemented |
| Error responses never include stack traces, SQL or exception text; unexpected errors become a generic `server_error` ([ERROR_HANDLING_AND_OBSERVABILITY.md](ERROR_HANDLING_AND_OBSERVABILITY.md)). | Implemented |
| A caller-supplied `X-Request-ID` is accepted only if it matches `[A-Za-z0-9._-]{1,64}`, which prevents log injection. | Implemented |
| Audit events (`AuditEvent`) record who did what to which object, without financial values. | Planned (Phase 1) |
| Error-tracking integrations (e.g. Sentry) must be opt-in, with personal data and request bodies scrubbed. | Planned |

## 10. Encryption

| Layer | Responsibility |
|---|---|
| In transit, client to server | TLS terminated at the reverse proxy; Django enforces HTTPS redirects and secure cookies in production. |
| In transit, app to database | `POSTGRES_SSLMODE` (`require` / `verify-full` when the database is remote). |
| At rest: database | Operator: encrypted disks or volumes, or a managed PostgreSQL service with encryption at rest. |
| At rest: private documents | Operator: encrypted filesystem or volume, or a bucket with server-side encryption once object storage is supported. |
| Backups | Operator: backups must be encrypted, access-controlled and restore-tested. They contain the same sensitive data as production. |
| Application-level field encryption | Not planned for the MVP. Reconsider for especially sensitive future fields (e.g. provider credentials). **Open.** |

## 11. Self-hosting responsibilities

Self-hosters operate a system that holds financial data. Finlume provides safe
defaults and startup checks; the operator is responsible for:

1. Running `python manage.py check --deploy` with production settings and resolving every finding (W004 is resolved by enabling HSTS once HTTPS is confirmed).
2. Terminating TLS with a maintained reverse proxy, and setting `FINLUME_TRUST_PROXY_SSL_HEADER=true` only behind that proxy.
3. Keeping PostgreSQL off the public internet, with strong credentials and TLS for remote connections.
4. Keeping the private storage directory outside every web-served path, which `finlume.E001` helps enforce.
5. Encrypted, tested backups and a retention policy that matches local law.
6. Applying Finlume and dependency security updates promptly. Watch the repository's security advisories.
7. Sharing a cache (e.g. Redis) between processes if they rely on the API throttle limits. The default local-memory cache counts each worker process separately (see [THREAT_MODEL.md](THREAT_MODEL.md)).
8. Not enabling external AI or data providers without informing users.

## 12. Supply chain

- **Locked dependencies:** pinned, hash-verified lock files are generated from `backend/pyproject.toml` with `uv pip compile` and installed with `pip --require-hashes` ([ADR-0004](../decisions/ADR-0004-dependency-management.md)). **Implemented.**
- **Dependency audit:** `pip-audit` runs in CI for runtime and development dependencies, and locally through `scripts/check.ps1` / `scripts/check.sh`. Example: DRF was upgraded from 3.16.1 to 3.18.3 after `pip-audit` flagged CVEs fixed in 3.18.2. **Implemented.**
- **Known exceptions:** none. The development-only `filelock` 4.1.0 advisory (Python 3.10 only) was resolved on 2026-10-27, when the Python floor was raised to 3.12.
- **Update pull requests:** Dependabot proposes weekly version updates for the backend, web client and GitHub Actions, and security updates only for the mobile client (`.github/dependabot.yml`). **Configured.** Dependabot alerts must also be enabled in the repository settings.
- **Static security checks:** Ruff's bandit-derived `S` rules run in CI. **Implemented.**
- **Workflow permissions:** CI uses `permissions: contents: read`. **Implemented.**
