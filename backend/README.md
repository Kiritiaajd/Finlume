# Finlume backend

Django + Django REST Framework modular monolith that serves the versioned
Finlume API (`/api/v1/`) and hosts the deterministic financial calculation
engine.

| Path | Layer | Purpose |
|------|-------|---------|
| `config/` | — | Django settings (per environment), root URLconf, ASGI/WSGI entry points. |
| `api/` | Presentation (shared) | DRF plumbing shared by every endpoint: the error envelope, pagination and permissions. |
| `apps/` | Presentation + persistence | Django apps: models, migrations and admin at the top level. Each app's endpoints (views, serializers, urls) are in its `api/` package. |
| `services/` | Application | Business workflows, one sub-package per capability (`access`, `accounts`, `organizations` and `workspaces` now; `statement_analysis`, `documents`, `stock_research` and `portfolio_analysis` later). Coordinates authorization, the ORM, the domain engine, providers and audit events. Never imports DRF. |
| `domain/` | Domain | Pure Python financial concepts, validation rules and calculations. No Django imports. |
| `infrastructure/` | Infrastructure | Adapters to external concerns (private file storage today; providers and jobs later). |
| `tests/` | — | pytest suite mirroring the layers above. |
| `requirements/` | — | Generated, hashed lock files. Do not edit by hand. |

Dependency direction: `apps` and `api` → `services` → `domain`. `infrastructure` is used
by `apps` and `services`. See
[`docs/architecture/DOMAIN_BOUNDARIES.md`](../docs/architecture/DOMAIN_BOUNDARIES.md).

Setup, commands and conventions are documented in
[`docs/development/LOCAL_SETUP.md`](../docs/development/LOCAL_SETUP.md).
