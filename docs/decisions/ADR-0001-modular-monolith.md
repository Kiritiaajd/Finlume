# ADR-0001: Modular monolith with layered modules

- **Status:** Accepted
- **Date:** 2026-10-25

## Context

Finlume will cover several financial domains: business statement analysis, personal finance, and investments and company research. Their data models, permissions and rules differ. The project is early-stage, open source and maintained by a small team, and it must remain easy to self-host.

Microservices would add network boundaries, distributed transactions, multiple deployables and operational overhead long before there is load or team size to justify them. An unstructured Django project, on the other hand, would let financial logic leak into views and serializers, making it hard to test and to trust.

## Decision

Build one deployable Django backend, structured as a **modular monolith** with four layers and a fixed dependency direction:

```text
apps/ (presentation: DRF views, serializers; persistence: models, migrations, admin)
  └─► application/ (use cases: coordinate domain logic and persistence)    [package named services/, see note]
        └─► domain/ (pure Python: financial concepts, validation, calculations)
infrastructure/ (adapters: storage, external providers, background jobs) ─► used by apps/application
```

- `domain/` imports nothing from Django, DRF, `apps`, `config` or `infrastructure`. This is enforced by `backend/tests/test_architecture.py`.
- Each Django app owns one module's models and API. Apps interact through explicit interfaces (services and querysets), not through each other's internals.
- Personal finance, business finance and investments become separate modules wherever their models or permissions differ. Shared infrastructure (accounts, workspaces, documents, audit) is shared only where the concepts genuinely match.
- New Django apps are created when their first model or endpoint is implemented, not in advance. The planned module map is in [DOMAIN_BOUNDARIES](../architecture/DOMAIN_BOUNDARIES.md).

## Consequences

### Positive
- Single deployment, single database transaction scope, simple local setup and self-hosting.
- Financial logic is testable without a database or HTTP layer.
- Module boundaries make a later extraction possible if it is ever needed.

### Negative
- Boundaries are enforced by convention, review and one architecture test, not by process isolation.
- One codebase scales as one unit (horizontally, via more application processes).

## Alternatives considered

- **Microservices** (for example, a separate calculation service): rejected as premature. They add latency, deployment complexity and consistency problems without a current benefit.
- **Conventional "fat models / fat views" Django:** rejected. It mixes arithmetic with HTTP and ORM concerns and makes calculations hard to verify.
- **Separate repositories for engine and API:** rejected for now. Atomic changes across the engine and its API are more valuable at this stage.

## Revisit when

- A module needs independent scaling or a different runtime, for example CPU-heavy PDF extraction. Consider moving it to a background worker first ([SCALABILITY_AND_DEPLOYMENT](../architecture/SCALABILITY_AND_DEPLOYMENT.md)).
- The calculation engine needs to be published as a standalone library.

## Note 2026-10-27: the application layer is `backend/services/`

The application layer was scaffolded for MVP step 1 under the package name **`services/`**,
with one sub-package per business **capability**: the tenancy ones now (`access`,
`accounts`, `organizations`, `workspaces`), and later `statement_analysis`, `documents`,
`stock_research` and `portfolio_analysis`
([DOMAIN_BOUNDARIES §3.3](../architecture/DOMAIN_BOUNDARIES.md#33-service-capabilities-backendservices)).
These are modules inside the one deployable, not microservices. The decision is unchanged:
same layer, same dependency direction, and no DRF imports, which `tests/test_architecture.py`
enforces. Only the package name differs from the diagram above.
