# ADR-0007: Authentication, sessions and login protection for the MVP

- **Status:** Accepted
- **Date:** 2026-10-27
- **Resolves:** foundation audit decisions A3 (FA-07), A5 (FA-20), A6 (FA-19) and A9 (FA-08)

## Context

MVP step 1 adds registration, login and logout to the API ([MVP plan](../development/MVP_IMPLEMENTATION_PLAN.md#step-1--workspace-ownership-and-authorisation)). The web client talks to the API from the same origin with Django sessions and CSRF ([ADR-0006](ADR-0006-client-stack.md)). The [foundation audit](../architecture/FOUNDATION_AUDIT.md#8-decisions-requiring-maintainer-approval) left four questions open that shape those endpoints:

- With only `SessionAuthentication`, DRF answers unauthenticated requests with `403`, because that class sends no `WWW-Authenticate` challenge. [Acceptance criterion 10](../product/PRODUCT_SCOPE.md#11-mvp-acceptance-criteria) expects `401`.
- `accounts.User` inherits `username` from `AbstractUser`. `email` is unique without regard to case, but it can be blank, and login uses `username`.
- Sessions use Django's default lifetime of two weeks, with no idle timeout. Finlume holds financial data, often on shared or office machines.
- Nothing limits repeated failed logins. DRF's default throttles (`60/minute` anonymous) are far too loose for password guessing.

## Decision

1. **Unauthenticated requests get `401`** (A3). The project's session authentication class subclasses DRF's `SessionAuthentication` and returns a `Session` challenge from `authenticate_header()`. DRF then answers `401 not_authenticated` and sets `WWW-Authenticate: Session`. A signed-in user without permission still gets `403 permission_denied`, a CSRF failure still gets `403`, and another workspace's object still gets `404`.
2. **Users sign in with their email address** (A5). An email-based authentication backend matches the address without regard to case, using the existing unique index. A database `CHECK (email <> '')` constraint makes email mandatory. `username` stays on the model for the Django admin and `createsuperuser`, but it is not a login identifier for the API.
3. **Sessions expire after 8 hours of inactivity** (A6). `SESSION_COOKIE_AGE` is 8 hours, configurable through `FINLUME_SESSION_AGE_SECONDS`. `SESSION_SAVE_EVERY_REQUEST = True` makes the expiry sliding. Logout and password change end the session server-side. There is no separate absolute lifetime in the MVP.
4. **Login is throttled with DRF's built-in throttles, with no new dependency** (A9).
   - The login view has its own scoped rates: `5/minute` per client IP and `5/minute` per submitted email. Both are configurable, and the sixth attempt gets `429 throttled` with `Retry-After`.
   - Each attempt writes an `auth.login` or `auth.login_failed` audit event. The event holds no password or other submitted value except the normalised email.
   - The Django admin login is not covered. Deployments keep the admin on a non-default path (`FINLUME_ADMIN_URL_PATH`) and restrict it at the reverse proxy. The deployment guide documents this.
   - Throttle counters stay per process until step 8 moves them to a shared cache (FA-09).

## Consequences

### Positive

- Status codes follow HTTP semantics, so the web and future mobile clients can tell "sign in again" (`401`) from "not allowed" (`403`) without inspecting the body.
- Email login matches what users expect and removes a second identifier they would have to remember.
- An unattended session expires the same working day.
- No new dependency is needed for login protection.

### Negative

- Step 1 has to change `test_anonymous_requests_are_rejected_by_default`, which pins `403` today, and the API conventions.
- Users must sign in again after 8 idle hours. Each authenticated request also writes the session row.
- A per-email throttle lets an attacker lock a known user out for a minute at a time. A per-IP limit alone would leave distributed guessing unchecked, so both apply.
- The admin login relies on deployment configuration rather than application code.

## Alternatives considered

- **Keep `403` and correct acceptance criterion 10:** less code, but clients would have to branch on `error.code` to know when to show the sign-in screen, and it differs from what the mobile client will need.
- **Token authentication now:** it suits mobile, but the web client does not need it and it adds token storage and revocation work. It stays open for the mobile phase (ARCHITECTURE_DECISIONS pending decision 2).
- **Username login:** it is the Django default, but users must remember another identifier and the email uniqueness constraint goes unused.
- **A lockout library such as django-axes:** it gives stronger admin coverage, but it is a new dependency with its own models and middleware. It can be reconsidered if the built-in throttles prove insufficient.

## Revisit when

- The mobile client starts: decide token or OIDC authentication and how it reports `401`.
- A hosted deployment is planned: add an absolute session lifetime, multi-factor authentication and stronger admin protection.
- Throttling moves to a shared cache (step 8): check that the rates hold across workers.
