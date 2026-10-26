# Finlume backend

Django + Django REST Framework modular monolith that serves the versioned
Finlume API (`/api/v1/`) and hosts the deterministic financial calculation
engine.

| Path | Layer | Purpose |
|------|-------|---------|
| `config/` | — | Django settings (per environment), root URLconf, ASGI/WSGI entry points. |
| `apps/` | Presentation + persistence | Django apps: models, migrations, admin, DRF views and serializers. |
| `domain/` | Domain | Pure Python financial concepts, validation rules and calculations. No Django imports. |
| `infrastructure/` | Infrastructure | Adapters to external concerns (private file storage today; providers and jobs later). |
| `tests/` | — | pytest suite mirroring the layers above. |
| `requirements/` | — | Generated, hashed lock files. Do not edit by hand. |

An `application/` package (use cases that coordinate domain logic and
persistence) is introduced together with the first use case: running a saved
analysis. See [`docs/architecture/DOMAIN_BOUNDARIES.md`](../docs/architecture/DOMAIN_BOUNDARIES.md).

Setup, commands and conventions are documented in
[`docs/development/LOCAL_SETUP.md`](../docs/development/LOCAL_SETUP.md).
