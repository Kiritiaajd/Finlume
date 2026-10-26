# ADR-0002: Backend stack — Django 5.2 LTS, DRF, PostgreSQL

- **Status:** Accepted
- **Date:** 2026-10-25

## Context

The backend needs mature authentication, an admin interface, migrations, a well-understood security model and a REST toolkit, all in Python so that it can host the financial engine directly. Financial values need exact decimal storage. At decision time, the only interpreter on the primary development machine is **Python 3.10.7**, and Python 3.10 reaches end-of-life in October 2026.

## Decision

- **Python + Django + Django REST Framework**, with PostgreSQL as the only supported production database.
- **Django 5.2 LTS** (currently 5.2.18), constrained to `>=5.2,<5.3`. It is the newest Django line that still supports Python 3.10, and it receives security fixes until **April 2028**.
- **DRF 3.18.x** (`>=3.18.2,<3.19`). 3.18.2 is the first release fixing the request-parsing and content-negotiation advisories that affect 3.16.
- **psycopg 3** (`psycopg[binary]`) as the PostgreSQL driver.
- **Python version policy:** `requires-python = ">=3.10"`, with CI testing the oldest supported version (3.10) and the newest targeted version (3.13). New environments should use 3.12 or 3.13. The minimum is raised deliberately, in its own PR, and recorded in `CHANGELOG.md`.
- SQLite is allowed only as an explicit development opt-in for throwaway trials and for fast, isolated local tests. Development defaults to PostgreSQL (since 2026-10-25), and production settings refuse to start with SQLite.

## Consequences

### Positive
- Batteries included: auth, admin, ORM and migrations, CSRF and session security, mature ecosystem.
- An LTS release gives a predictable 18-month window before a forced major upgrade.
- PostgreSQL `numeric` stores money exactly; constraints and transactions protect financial records.

### Negative
- Django 6.x features are unavailable until the Python floor rises to 3.12.
- Python 3.10 is end-of-life this month, and it already blocks one dev-tool security fix: `filelock` ≥ 4.2.1 needs Python ≥ 3.11.
- Synchronous Django request handling. Long-running work must move to background jobs when it appears.

## Alternatives considered

- **Django 6.x:** requires Python ≥ 3.12, which is not installed locally. Revisit with the Python floor.
- **FastAPI:** excluded by project constraint. It would also mean assembling auth, admin and migrations separately.
- **Java/Spring:** excluded by project constraint. It would also split the language between the engine and the API.
- **SQLite or MySQL in production:** SQLite lacks the concurrency and exact `numeric` behaviour needed. PostgreSQL is the most capable open-source option for this workload.

## Revisit when

- **Decision required now:** raise `requires-python` to `>=3.12` once contributors have Python 3.12+. This drops 3.10 (EOL), clears the dev-tool advisory, and allows Django 6.x LTS planning.
- Django 5.2 approaches end of support (April 2028).
