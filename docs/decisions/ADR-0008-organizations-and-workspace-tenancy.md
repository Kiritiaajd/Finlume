# ADR-0008: Organizations and workspace tenancy

- **Status:** Proposed. Awaiting maintainer approval
- **Date:** 2026-10-27
- **Implementation plan:** [TENANCY_IMPLEMENTATION_PLAN](../development/TENANCY_IMPLEMENTATION_PLAN.md)

## Context

Finlume must support individual users and organizations while keeping financial data isolated between users and workspaces.

The backend remains a modular monolith ([ADR-0001](ADR-0001-modular-monolith.md)). Organizations represent customer boundaries; workspaces represent contexts in which financial work occurs. Organization membership does not automatically grant access to organizational workspaces, including for organization administrators.

Until now, the data model treated the workspace as the only tenancy boundary and listed `Organization` as a future grouping. Introducing organizations later would have meant migrating every business workspace, so the model is settled before the first tenancy migration (MVP step 1).

## Decision

### 1. Organization creation

Any authenticated user may create an organization. The creator receives the organization administrator role. Creation and initial membership assignment occur atomically.

### 2. Workspace creation

Personal workspaces are created during registration and remain outside any organization.

Any active organization member may create a workspace within that organization. The creator becomes the workspace owner and is automatically added as an owner member in the same transaction.

Organization workspaces may have one or multiple members. Workspace access is determined by explicit workspace membership, not by organization membership.

### 3. Ownership and membership invariants

Every workspace must have at least one owner. Every organization must have at least one administrator.

A user cannot leave or be removed from an organization if doing so would leave an organizational workspace without an owner. Ownership must first be transferred to another eligible workspace member.

Organization membership removal and corresponding workspace membership changes occur in one database transaction. A failed invariant check rolls back the entire operation.

Organization administrators do not automatically become workspace owners or gain access to workspace data. Any exceptional ownership recovery process must be explicitly authorized, audited and implemented separately. The planned process is an operator-only management command with a mandatory reason and an audit event ([plan §3](../development/TENANCY_IMPLEMENTATION_PLAN.md#ownership-recovery-exceptional-cases-only)).

### 4. Personal workspace privacy

Each user has exactly one personal workspace. The user is its only member and owner.

Personal workspaces cannot be shared or joined by other users in this phase. Collaboration occurs in organizational workspaces.

### 5. Team deferral

Teams and team-based workspace grants are deferred. The initial implementation uses direct workspace membership. Team access may be added later without changing the underlying organization and workspace ownership model.

### 6. Authorization and isolation

Workspace-scoped endpoints use a shared authorization resolver. A user without workspace membership receives `404 Not Found`; a workspace member lacking the required role receives `403 Forbidden`.

Every tenant-resource queryset is scoped to the authorized workspace. The same isolation requirements apply to downloads, exports, writes and background jobs. Every tenant resource is therefore addressed under its workspace (`/api/v1/workspaces/{id}/…`), so one resolver covers every endpoint.

Organization membership is kept synchronized with organizational workspace membership so that a single indexed workspace-membership lookup can authorize workspace access. This invariant must be preserved by every supported mutation path.

### 7. Data integrity and deletion

Database constraints enforce uniqueness and mutually exclusive workspace ownership links wherever expressible. Application use cases enforce cross-table invariants within transactions.

Direct administrative deletion must not bypass ownership or data-retention safeguards. Organization, workspace and user deletion must use approved lifecycle workflows. Until those workflows exist (MVP step 8), the Django admin shows tenancy records read-only and cannot delete users.

Existing users must receive their required personal workspaces and owner memberships through a tested data migration. Users created outside registration, such as with `createsuperuser`, receive theirs when they first sign in.

## Consequences

### Positive

- One Django deployment and one primary database remain sufficient.
- Workspace membership is the authoritative boundary for workspace data access.
- Organization administrators cannot inspect workspaces merely by virtue of their organization role.
- Teams, invitations and reviewer roles can be introduced incrementally.

### Negative

- Cross-table invariants require transactional application logic and tests in addition to database constraints.
- Query-count targets are verified against PostgreSQL rather than assumed from ORM structure.
- Every tenant URL carries the workspace ID, which makes URLs longer.
- Until step 8, deleting tenancy data or users needs an operator, not the admin interface.

## Alternatives considered

- **Workspace as the only boundary, with organizations later** (the previous data model): fewer tables now, but every business workspace would need migrating once organizations arrive, and the customer boundary would not exist in the meantime.
- **Every workspace belongs to an organization, with a personal workspace inside each organization:** simpler for organization-only customers, but individual users would have to create an organization before they could do anything.
- **Organization membership grants access to all of the organization's workspaces:** simpler checks, but it breaks least privilege and the requirement that admins cannot read private workspaces.
- **Checking organization membership on every request** instead of keeping memberships synchronized: no synchronization logic, but a second query or join on every workspace request.
- **Teams now:** extra models and synchronization rules with no current user need.

## Revisit when

- Organizations need teams, invitations or a reviewer role.
- A hosted, multi-tenant offering is planned (decision D-08). Organization verification, subscription limits and stronger recovery controls may then be needed.
- A workspace must move between organizations, or a personal workspace must become shared.

## Implementation sequence

1. PR 0: record this decision and update architecture, data-model, product-scope and API documentation.
2. PR 1a: implement tenancy models, constraints and authorization helpers.
3. PR 1b: implement authentication, registration, personal workspace creation and audit logging.
4. PR 1c: implement workspace APIs, membership management and isolation tests.
5. PR 1d: implement organization APIs, membership synchronization and organization-level invariant tests.

Each implementation pull request must pass the existing CI suite and the acceptance tests defined in [TENANCY_IMPLEMENTATION_PLAN.md](../development/TENANCY_IMPLEMENTATION_PLAN.md).
