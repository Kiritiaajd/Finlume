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
support until April 2028, and it supports the Python 3.10 interpreter available today.
Django 6.x requires Python 3.12+. Locked versions: Django 5.2.18, DRF 3.18.3
(chosen because it fixes request-parsing CVEs present in 3.16), psycopg 3.3.6. FastAPI and
Java are explicitly out of scope as the primary backend. The Python floor is 3.10 for now;
3.12 or 3.13 is recommended (see pending decisions).

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

## Decisions pending approval

These are open and need a maintainer decision before or during the phase noted.

| # | Decision | Context | Needed by |
|---|----------|---------|-----------|
| 1 | **Raise the Python floor to 3.12** | Python 3.10 reaches end-of-life in October 2026. Development-only `filelock` advisories cannot be fixed on 3.10 because the fixed release needs 3.11+. Django 6.x requires 3.12+. Raising the floor needs a newer local interpreter. | As soon as practical, ideally before Phase 1 work starts |
| 2 | **Mobile authentication** | Session cookies suit the same-origin web app, but not native apps. Candidates are expiring, revocable API tokens or OAuth 2.0 / OIDC. | Before the mobile phase |
| 3 | **Foreign-exchange policy** | The MVP analyses each fact set in a single currency and never converts. Cross-currency comparison needs a rate source, rate dates and a methodology. | Before multi-currency comparison or portfolios |
| 4 | **Line-item taxonomy extension** | The MVP taxonomy is a fixed `LineItem` enum. Industry-specific items (banks, insurers) and user-defined mappings need an extension model. | Late Phase 1 / Phase 2 |
| 5 | **Retention periods** | Defaults for deleted-account grace periods, audit-event retention and backup retention. See [DATA_LIFECYCLE_AND_RETENTION.md](../data/DATA_LIFECYCLE_AND_RETENTION.md). | Before any hosted deployment |
| 6 | **Hosting model** | Self-hosted only, or also an official hosted instance. A hosted instance brings legal, privacy and operational obligations. | Before a public launch |
| 7 | **Security and Code of Conduct contacts** | A private reporting channel (GitHub private vulnerability reporting must be enabled) and an enforcement contact for the Code of Conduct. | Before inviting outside contributors |
