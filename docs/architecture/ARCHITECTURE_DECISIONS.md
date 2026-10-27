# Architecture Decisions

This page indexes Finlume's Architecture Decision Records (ADRs) and lists decisions that
still need maintainer approval. Each ADR in [`docs/decisions/`](../decisions/) records
context, the decision, alternatives considered, and consequences.

## How decisions are made

- A change that is hard to reverse or that shapes how contributors work gets an ADR:
  a new framework, a datastore, a layer rule, a security boundary, or a calculation
  convention.
- ADRs are numbered sequentially (`ADR-NNNN-short-title.md`) and never renumbered.
- An accepted ADR is not edited to change its decision. A new ADR supersedes it, and the
  old one is marked `Superseded by ADR-NNNN`.
- Statuses: `Proposed`, `Accepted`, `Superseded`, `Rejected`.

## Decision index

| ADR | Title | Status |
|-----|-------|--------|
| [ADR-0001](../decisions/ADR-0001-modular-monolith.md) | Modular monolith | Accepted |
| [ADR-0002](../decisions/ADR-0002-backend-stack.md) | Backend stack: Django 5.2 LTS, DRF, PostgreSQL | Accepted |
| [ADR-0003](../decisions/ADR-0003-deterministic-calculation-engine.md) | Deterministic calculation engine | Accepted |
| [ADR-0004](../decisions/ADR-0004-dependency-management.md) | Dependency management and lock files | Accepted |
| [ADR-0005](../decisions/ADR-0005-private-document-storage.md) | Private document storage | Accepted |
| [ADR-0006](../decisions/ADR-0006-client-stack.md) | Web and mobile client stack | Accepted (direction; not yet implemented) |
| [ADR-0007](../decisions/ADR-0007-authentication-and-sessions.md) | Authentication, sessions and login protection for the MVP | Accepted; implemented (MVP PR 1b) |
| [ADR-0008](../decisions/ADR-0008-organizations-and-workspace-tenancy.md) | Organizations and workspace tenancy | Proposed |

### ADR-0001 — Modular monolith

Finlume ships as **one Django deployable** with explicit internal module boundaries, not as
microservices. A small open-source project gains nothing from distributed transactions,
network failure modes, or multi-service deployment, and self-hosters need something they
can run on one machine. Boundaries are enforced in code instead. Django apps own
persistence and HTTP for one module, the pure `domain` package cannot import frameworks
(a test checks this), and modules talk through the application layer rather than reaching
into each other's models. A module is extracted into a separate service only when a
measured need appears, such as independent scaling or isolation of untrusted document
parsing.

### ADR-0002 — Backend stack

The backend uses **Python, Django 5.2 LTS, Django REST Framework and PostgreSQL**. Django
supplies a mature ORM and migrations, authentication, an admin, and strong security
defaults. DRF supplies serializers, versioning, throttling and pagination. PostgreSQL's
`numeric` type preserves exact decimals. Django 5.2 is the current LTS, with security
support until April 2028. Locked versions: Django 5.2.18, DRF 3.18.3
(chosen because it fixes request-parsing CVEs present in 3.16), psycopg 3.3.6. FastAPI and
Java are explicitly out of scope as the primary backend. The Python floor is **3.12**
(raised from 3.10 on 2026-10-27), and CI tests 3.12 and 3.13. That also leaves Django 6.x
open as a later upgrade.

### ADR-0003 — Deterministic calculation engine

Financial arithmetic lives in `backend/domain/` as ordinary, framework-independent Python
that is **deterministic and versioned**. Money is `decimal.Decimal`, never `float`.
Calculations run in an explicit decimal context (precision 34, `ROUND_HALF_EVEN`, with
traps for invalid operations), so results cannot depend on a caller's ambient context.
Scaling from thousands, lakhs, crores and so on is exact. Missing inputs are reported,
never assumed zero. Every result carries its methodology text, and every analysis carries
`ENGINE_VERSION` (currently `0.1.0`), which is bumped whenever any output could change. AI
may explain results but never produces financial figures.

### ADR-0004 — Dependency management

`backend/pyproject.toml` is the single place where dependencies are declared. Hashed,
cross-platform lock files are generated from it with
`uv pip compile --universal --generate-hashes` into `backend/requirements/base.txt`
(runtime) and `backend/requirements/dev.txt` (development). Anyone installs with plain
`pip install --require-hashes -r ...`; `uv` is needed only to regenerate the locks and is
itself pinned in the dev lock. CI checks that the locks match `pyproject.toml` and audits
both with `pip-audit`. No other dependency manifest exists.

### ADR-0005 — Private document storage

Uploaded financial documents are **never publicly addressable**.
`PrivateFileSystemStorage` writes owner-only files and refuses to produce URLs. Both the
`default` and `private_documents` storage aliases use it, so a model field that forgets to
name a storage still stays private. The `finlume.E001` system check rejects a private root
placed inside a static or media root. Files reach users only through authenticated,
ownership-checked API views. Object storage with private buckets and short-lived signed
URLs can replace the filesystem adapter through the `STORAGES` setting without changing
callers.

### ADR-0006 — Client stack (accepted; shells scaffolded 2026-10-25)

The web client will use **React + TypeScript + Vite**, with TanStack Query for server
state, React Hook Form + Zod for forms, Apache ECharts for charts, and Tailwind CSS +
shadcn/ui for components. The mobile client will use **React Native + Expo**. Both consume
the same `/api/v1/` API. Both now exist as shells with a live health check and honest empty
states ([Frontend applications](../development/FRONTEND.md)). Web data features come in
Phase 1, and mobile data features after the v1 API stabilises post-MVP. In
development the web app reaches the API through the Vite dev proxy and in production
through the same-origin reverse proxy, so no CORS dependency is needed for the web client.

### ADR-0007 — Authentication and sessions (accepted 2026-10-27)

Users sign in to the API with their **email address** and a password, using Django
sessions. Unauthenticated requests get **`401`** with a `WWW-Authenticate: Session`
challenge, while authenticated requests without permission get `403`. Sessions expire after
**8 hours of inactivity** (sliding, configurable). Login is limited with DRF's built-in
scoped throttles: **5 attempts per minute** per client IP and per email, with audit events
for each attempt and no new dependency. The Django admin login is protected at deployment
by a non-default path and reverse-proxy restrictions.

### ADR-0008 — Organizations and workspace tenancy (proposed 2026-10-27)

**Organizations** are the customer boundary, and **workspaces** are where financial work
happens. Every user has one private personal workspace, outside any organization. Any
organization member can create an organization workspace and becomes its owner. Access
comes **only** from workspace membership: organization admins cannot read a workspace they
are not a member of. One resolver authorises every request with a single indexed query,
because organization and workspace memberships are kept synchronised. Every tenant resource
is nested under `/workspaces/{id}/`, so non-members get `404` and members without the
required role get `403`. Last-owner and last-admin rules are enforced in transactions.
Recovery for workspaces whose owners are all deactivated is an audited, operator-only
command. Teams are deferred. Plan:
[TENANCY_IMPLEMENTATION_PLAN](../development/TENANCY_IMPLEMENTATION_PLAN.md).

### Smaller conventions decided 2026-10-27

- The MVP app for workspaces and memberships is named **`workspaces`** (FA-26). Under the proposed [ADR-0008](../decisions/ADR-0008-organizations-and-workspace-tenancy.md), `organizations` holds the `Organization` customer boundary from MVP step 1.
- The retention defaults in [DATA_LIFECYCLE_AND_RETENTION §7](../data/DATA_LIFECYCLE_AND_RETENTION.md#7-retention-periods) are approved: a 30-day workspace deletion grace period, 1 year for audit events, 30 days for logs and 35 days for backups. All of them are configurable by self-hosters (D-07).

## Decisions pending approval

These are open and need a maintainer decision before or during the phase noted.

| # | Decision | Context | Needed by |
|---|----------|---------|-----------|
| 1 | ~~Raise the Python floor to 3.12~~ | **Done 2026-10-27** ([ADR-0002 update](../decisions/ADR-0002-backend-stack.md#update-2026-10-27-python-floor-raised-to-312)). | — |
| 2 | **Mobile authentication** | Session cookies suit the same-origin web app, but not native apps. Candidates are expiring, revocable API tokens or OAuth 2.0 / OIDC. | Before the mobile phase |
| 3 | **Foreign-exchange policy** | The MVP analyses each fact set in a single currency and never converts. Cross-currency comparison needs a rate source, rate dates and a methodology. | Before multi-currency comparison or portfolios |
| 4 | **Line-item taxonomy extension** | The MVP taxonomy is a fixed `LineItem` enum. Industry-specific items (banks, insurers) and user-defined mappings need an extension model. | Late Phase 1 / Phase 2 |
| 5 | ~~Retention periods~~ | **Decided 2026-10-27**: the proposed defaults are approved (see above). | — |
| 6 | **Hosting model** | Self-hosted only, or also an official hosted instance. A hosted instance brings legal, privacy and operational obligations. | Before a public launch |
| 7 | **Security and Code of Conduct contacts** | A private reporting channel (GitHub private vulnerability reporting must be enabled) and an enforcement contact for the Code of Conduct. | Before inviting outside contributors |
