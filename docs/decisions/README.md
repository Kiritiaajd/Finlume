# Architecture decision records

An ADR records one significant decision: its context, the decision itself, its consequences, and the alternatives considered. ADRs are append-only history. When a decision changes, write a new ADR that supersedes the old one, and update the old one's status rather than rewriting it.

A summary of all decisions, including smaller conventions that do not need their own ADR, is in [ARCHITECTURE_DECISIONS.md](../architecture/ARCHITECTURE_DECISIONS.md).

## Index

| ADR | Title | Status |
|-----|-------|--------|
| [0001](ADR-0001-modular-monolith.md) | Modular monolith with layered modules | Accepted |
| [0002](ADR-0002-backend-stack.md) | Backend stack: Django 5.2 LTS, DRF, PostgreSQL | Accepted |
| [0003](ADR-0003-deterministic-calculation-engine.md) | Deterministic, framework-independent calculation engine | Accepted |
| [0004](ADR-0004-dependency-management.md) | Dependency management: pyproject.toml + hashed uv-compiled locks | Accepted |
| [0005](ADR-0005-private-document-storage.md) | Private storage for uploaded financial documents | Accepted |
| [0006](ADR-0006-client-stack.md) | Web and mobile client stack | Accepted (direction; not implemented) |

## When to write an ADR

Write one when a decision:
- is costly to reverse (framework, database, data model foundations, authentication approach);
- changes a dependency direction or module boundary;
- adds infrastructure (queues, caches, external services, paid APIs);
- changes how financial values are calculated, rounded or stored.

## How to propose one

1. Copy the template below to `ADR-NNNN-short-title.md`, using the next free number.
2. Set the status to **Proposed** and open a pull request (`docs(adr): ...`).
3. Discuss in the PR. A maintainer marks it **Accepted** or **Rejected** before merging.
4. Add it to the index above.

Statuses: Proposed, Accepted, Rejected, Deprecated, Superseded by ADR-NNNN.

## Template

```markdown
# ADR-NNNN: Title

- **Status:** Proposed
- **Date:** YYYY-MM-DD

## Context
What forces are at play? What problem needs a decision?

## Decision
What we will do, stated plainly.

## Consequences
### Positive
### Negative

## Alternatives considered
Each option and why it was not chosen.

## Revisit when
The conditions that should trigger reconsidering this decision.
```
