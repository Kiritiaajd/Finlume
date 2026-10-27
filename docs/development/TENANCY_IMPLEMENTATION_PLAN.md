# Tenancy Implementation Plan: Organizations, Workspaces and Access Control

| | |
|---|---|
| Status | **Proposed**, with [ADR-0008](../decisions/ADR-0008-organizations-and-workspace-tenancy.md). Plan only; nothing here is implemented yet. The open questions were decided on 2026-10-27 ([§10](#10-decisions-2026-10-27)) |
| Date | 2026-10-27 |
| Replaces | The scope of [MVP plan step 1](MVP_IMPLEMENTATION_PLAN.md#step-1--workspace-ownership-and-authorisation). Steps 2–8 are unchanged, except that they build on this tenancy model |
| Builds on | [ADR-0001 modular monolith](../decisions/ADR-0001-modular-monolith.md) · [ADR-0007 authentication](../decisions/ADR-0007-authentication-and-sessions.md) · [Domain boundaries](../architecture/DOMAIN_BOUNDARIES.md) · [Data model](../data/DATA_MODEL.md) |

This plan adds **organizations** (the customer boundary) and **workspaces** (where financial
work happens), with one server-side access check that every later module reuses. It follows
the proposed modular-monolith direction but stays within the conventions the codebase already
has. It also cuts every part that would add code without adding protection or features the
MVP needs.

---

## 1. Design goals

1. **One access rule, in one place.** Every request for tenant data costs **one indexed
   query** for authorization. No view repeats the rule.
2. **Isolation by construction.** Tenant resources live under `/workspaces/{id}/…`, and their
   querysets are always filtered by the resolved workspace. Without workspace access, another
   workspace's object cannot be loaded, so the API answers `404`.
3. **The smallest model that supports both individual users and organizations.** No columns,
   statuses or apps without a feature that uses them.
4. **Keep the existing layering.** Views are thin, use cases live in `backend/services/`,
   arithmetic stays in `backend/domain/`, and the ORM is used directly (see §7).
5. **Proven by tests.** Every security case is a test, every key endpoint has a query-count
   budget, and constraints are verified on PostgreSQL in CI.

## 2. What is adopted, changed or deferred from the proposal

| Proposal | Decision | Why |
|---|---|---|
| Modular monolith, one Django deployable | **Adopt** (already ADR-0001) | — |
| `Organization` as the customer boundary | **Adopt now** (it was "Future" in DATA_MODEL) | Organizations need it, and adding it later would mean migrating every workspace |
| Personal workspace outside any organization | **Adopt** | Individual users (U1, U2) need it without creating an organization |
| Organization membership does not grant workspace access | **Adopt** | Least privilege; matches the proposal's User C example |
| Organization admin is not implicitly a workspace owner | **Adopt** | Same |
| Workspace `type` = private / shared | **Drop** | Access always comes from membership. A "private" workspace is one with a single member, so a type column would add states without adding rules |
| `status` on organizations and memberships | **Defer** | Only needed for invitations or suspension, which the MVP does not have. A membership either exists or it doesn't |
| `settings` JSON on organizations | **Defer** | No setting exists yet |
| `Team`, `TeamMembership` | **Defer** (design sketch in §9) | Teams only add value once they grant access. That is one change in the access resolver, made when there is a need |
| Reviewer role | **Defer to Phase 2** | Review is a Phase 2 workflow (PDF extraction). MVP CSV mapping is confirmed by editors |
| Email invitations | **Defer** | They need email delivery. The MVP adds existing users (FR-004) |
| `collection` app with `Dataset` and `CollectionJob` | **Map to existing modules** | `documents` (`SourceDocument`) and `ingestion` already cover uploads and imports. A generic `Dataset` would break data-model principle 1, and jobs arrive with Phase 2 |
| `POST /collection/jobs/` (not nested) | **Change** to nested routes | Every tenant resource sits under `/workspaces/{id}/` so the single access check applies |
| `services/`, `selectors.py`, `api/` and `tests/` folders inside every app | **Change** | One top-level `backend/services/` package holds all business workflows, with a sub-package per capability. This is ADR-0001's application layer. Tests stay in `backend/tests/`, as the codebase already does |

## 3. Data model

All four tables use the [standard columns](../data/DATABASE_CONVENTIONS.md#standard-columns):
internal `id`, `public_id` (UUID, the only identifier in URLs), `created_at` and `updated_at`.
They come from one abstract base, `apps.core.models.PublicModel`, which creates no table.

```text
User ──< OrganizationMembership >── Organization ──< Workspace (organization workspace)
  │                                                     │
  ├──< WorkspaceMembership >────────────────────────────┤
  └──── personal_owner (1:1) ─────────────────── Workspace (personal workspace)
```

### `organizations.Organization`

| Field | Type | Notes |
|---|---|---|
| `name` | varchar(200) | |
| `created_by` | FK → User, `SET NULL`, nullable | |

### `organizations.OrganizationMembership`

| Field | Type | Notes |
|---|---|---|
| `organization` | FK → Organization, `CASCADE` | Django's FK index serves "members of this organization" |
| `user` | FK → User, `CASCADE` | |
| `role` | varchar(16), `TextChoices` + CHECK | `admin` or `member` |

Constraint: `UNIQUE (user, organization)`. Its leading `user` column also serves "my
organizations".

### `workspaces.Workspace`

| Field | Type | Notes |
|---|---|---|
| `name` | varchar(200) | |
| `organization` | FK → Organization, `CASCADE`, nullable | Set for organization workspaces |
| `personal_owner` | FK → User, `CASCADE`, nullable, **unique** | Set for personal workspaces; one per user |
| `created_by` | FK → User, `SET NULL`, nullable | |

Constraint: exactly one of `organization` and `personal_owner` is set:

```python
models.CheckConstraint(
    condition=Q(organization__isnull=True, personal_owner__isnull=False)
    | Q(organization__isnull=False, personal_owner__isnull=True),
    name="workspaces_workspace_one_owner_kind",
)
```

This replaces the planned `kind` column. The kind is derived (`is_personal` property), so the
two can never disagree. `base_currency` from DATA_MODEL §4.2 is added in step 3, when
statements first use it.

### `workspaces.WorkspaceMembership`

| Field | Type | Notes |
|---|---|---|
| `workspace` | FK → Workspace, `CASCADE` | FK index serves "members of this workspace" |
| `user` | FK → User, `CASCADE` | |
| `role` | varchar(16), `TextChoices` + CHECK | `owner`, `editor` or `viewer` |

Constraint: `UNIQUE (user, workspace)`. This is the index the access check uses.

### Invariants, enforced in use cases and covered by tests

| # | Invariant | Enforced by |
|---|---|---|
| I1 | Every user has exactly one personal workspace, and is its only member, as owner | `register_user` creates the user, workspace and membership in one transaction. A data migration backfills existing users. Sign-in calls the idempotent `ensure_personal_workspace` (one indexed query) for users created by `createsuperuser` or the admin. Personal workspaces reject new members |
| I2 | A user can be a member of an organization workspace only while they are a member of its organization | Adding a member checks organization membership. Removing a user from an organization deletes their memberships in its workspaces in the same transaction |
| I3 | A workspace always has at least one owner | Role changes and removals lock the workspace row (`select_for_update`) and then count owners. This prevents two concurrent demotions from both passing |
| I4 | An organization always has at least one admin | Same pattern, locking the organization row |
| I5 | Creating a workspace also makes its creator the owner, in the same transaction | `create_workspace` inserts the workspace and the owner membership together. A workspace without a membership row is never committed |
| I6 | Only active accounts (`User.is_active`) can sign in or be added as members | `EmailBackend` uses Django's `user_can_authenticate`, and the add-member use cases reject inactive users. A deactivated user keeps their memberships, but can do nothing with them until reactivated |

**Why I2 matters for speed:** because of I2, workspace membership alone proves access. The
per-request check never needs an organization-membership query.

### Roles and permissions

| Action | Viewer | Editor | Owner | Org member | Org admin |
|---|---|---|---|---|---|
| Read workspace data | ✓ | ✓ | ✓ | only via workspace membership | only via workspace membership |
| Create or edit statements, imports and runs (steps 2–5) | | ✓ | ✓ | | |
| Rename workspace; manage its members and roles | | | ✓ | | |
| Create a workspace in the organization (creator becomes owner) | | | | ✓ | ✓ |
| Rename organization; add, remove or change organization members | | | | | ✓ |

Role order for "at least" checks: `viewer < editor < owner`. It lives in one mapping in
`services/access/resolvers.py`, so role names are never compared ad hoc in views.

### Ownership recovery (exceptional cases only)

I3 keeps a workspace from losing its last owner through the API, but it cannot help when
every owner's account is **deactivated**, for example after someone leaves the company or a
compromised account is locked. Recovery is a deliberate operator action, **not** an
organization-admin power:

- It is a management command, `python manage.py recover_workspace_owner <workspace_id> <user_email> --reason "…"`, run by whoever operates the instance. It has no API endpoint, so no web session, including an organization admin's, can trigger it.
- It refuses unless all of the following hold:
  - the workspace belongs to an organization;
  - none of its owners has an active account;
  - the target user is active and a member of that organization;
  - a non-empty `--reason` is given.
- In one transaction, it makes the target user an owner (adding a membership if needed) and records an audit event `workspace.ownership_recovered`. The event holds the workspace, the new owner, the previous owners' `public_id`s, the reason and the operating-system user who ran the command. The command prints the event ID.
- The workspace's remaining members can see the event once workspace activity is exposed. Recovery is therefore never silent, and it grants access to exactly one named person, not to "the admins".
- It adds about 40 lines and a test for each refusal case. It ships in PR 1c.

## 4. Access control: one resolver, one mixin

### `backend/services/access/resolvers.py` (no DRF imports)

```python
_RANK = {WorkspaceRole.VIEWER: 0, WorkspaceRole.EDITOR: 1, WorkspaceRole.OWNER: 2}

def require_workspace_role(user: User, workspace_id: UUID, minimum: WorkspaceRole) -> WorkspaceMembership:
    """One query: the caller's membership joined to its workspace.

    No membership → Http404, so existence is not revealed.
    Membership with a lower role → PermissionDenied (403).
    """
    membership = (
        WorkspaceMembership.objects.select_related("workspace")
        .filter(user=user, workspace__public_id=workspace_id)
        .first()
    )
    if membership is None:
        raise Http404
    if _RANK[membership.role] < _RANK[minimum]:
        raise PermissionDenied
    return membership

def workspaces_for(user: User) -> QuerySet[Workspace]:
    return Workspace.objects.filter(memberships__user=user).annotate(my_role=F("memberships__role"))
```

`require_organization_role` follows the same pattern for organization endpoints. The existing
error handler ([`api/exceptions.py`](../../backend/api/exceptions.py)) already maps
Django's `Http404` and `PermissionDenied` to the standard envelope, so **no new error-mapping
code** is needed for them. The only addition is `services/errors.py` with a `ConflictError`
(for I3 and I4), mapped once to `409 conflict`.

### `apps/workspaces/scoping.py`: the one helper other apps import

```python
class WorkspaceScopedMixin:
    """Resolves the workspace once per request and scopes every queryset to it."""
    write_role = WorkspaceRole.EDITOR  # an owner-only view sets OWNER

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)  # authentication, permissions, throttles
        minimum = WorkspaceRole.VIEWER if request.method in SAFE_METHODS else self.write_role
        self.membership = require_workspace_role(request.user, kwargs["workspace_id"], minimum)
        self.workspace = self.membership.workspace

    def get_queryset(self):
        return super().get_queryset().filter(workspace=self.workspace)
```

Every tenant view in steps 2–8 (statements, documents, imports, analyses, reports) inherits
this mixin. Downloads, exports and future background jobs call `require_workspace_role` with
the initiating user before touching data. The proposal's flow (authenticate → load → check
membership → check role) therefore runs in one query, followed by a scoped object fetch.

### Query budget per request

These are enforced with pytest-django's `django_assert_num_queries`, with no new dependency.

| Request | Queries beyond session and user |
|---|---|
| Any workspace-scoped detail (`GET /workspaces/{id}/…/{obj}/`) | 1 membership + 1 object |
| Workspace-scoped list | 1 membership + 1 page + 1 count |
| `GET /workspaces/` (my workspaces, with my role) | 1 page + 1 count |
| `GET /workspaces/{id}/members/` | 1 membership + 1 page (`select_related("user")`) + 1 count |

Email lookups (login, adding an organization member) filter through
`alias(email_lower=Lower("email")).filter(email_lower=…)`, so they use the existing
`accounts_user_email_ci_unique` expression index. `email__iexact` would not use it on
PostgreSQL.

## 5. API surface (v1)

Paths are relative to `/api/v1/`. Users, organizations and workspaces are identified by
`public_id`. Lists are paginated, and errors use the standard envelope.

| Area | Endpoints | Minimum role |
|---|---|---|
| Auth (ADR-0007) | `GET auth/csrf/` · `POST auth/register/` · `POST auth/login/` · `POST auth/logout/` · `GET me/` | public (csrf, register, login); signed in (logout, me) |
| Organizations | `GET, POST organizations/` · `GET, PATCH organizations/{id}/` | signed in · member (GET) / admin (PATCH) |
| Organization members | `GET, POST organizations/{id}/members/` · `PATCH, DELETE organizations/{id}/members/{user_id}/` | member (GET) / admin (writes); a member may `DELETE` themselves (leave) |
| Workspaces | `GET, POST workspaces/` · `GET, PATCH workspaces/{id}/` | signed in (POST requires `organization` and organization membership) · viewer (GET) / owner (PATCH) |
| Workspace members | `GET, POST workspaces/{id}/members/` · `PATCH, DELETE workspaces/{id}/members/{user_id}/` | viewer (GET) / owner (writes); a member may `DELETE` themselves (leave) |

Notes:

- Personal workspaces are created only at registration. `POST workspaces/` always creates an
  organization workspace.
- Workspace members are added by `user_id`, and must already be members of the organization
  (I2). Users can only be picked from a list they are allowed to see, so the workspace
  endpoints never reveal whether an email address is registered.
- Organization members are added by email, so that endpoint can reveal whether an address is
  registered. It is admin-only and gets its own throttle scope. Invitations by email replace
  it later.
- Ownership transfer is a `PATCH` that sets another member's role to `owner`, so it needs no
  extra endpoint.
- Delete endpoints for organizations and workspaces arrive with export and deletion in step 8
  (FR-054, FR-055, the A8 grace period). Until then, nothing deletes them through the
  application: the Django admin shows the four tenancy models read-only, and user deletion is
  disabled in `FinlumeUserAdmin`, because both would bypass I2–I4 (ADR-0008 §7).
- Every later tenant resource is also nested under its workspace, for example
  `workspaces/{id}/statements/{id}/line-items/`, with at most one level below the workspace
  collection ([API conventions](../api/API_CONVENTIONS.md#resources-and-urls)).

## 6. Code layout

The scaffold below **exists** (created 2026-10-27). Each file holds only a docstring stating
its responsibility, plus the configuration Django needs: `AppConfig`, empty `urlpatterns` and
`migrations/`. The code arrives in PRs 1a–1d.

`backend/services/` is the **application layer** of ADR-0001: every business workflow lives
there, in one sub-package per **capability**. This step needs only the tenancy capabilities.
The financial ones (`statement_analysis`, `documents`, `stock_research`,
`portfolio_analysis`) are created with their first feature, not as empty folders
([DOMAIN_BOUNDARIES §3.3](../architecture/DOMAIN_BOUNDARIES.md#33-service-capabilities-backendservices)).

```text
backend/
├── services/                    # business workflows, one sub-package per capability
│   ├── __init__.py              # layer rules and the capability list
│   ├── errors.py                # ConflictError → 409 conflict
│   ├── access/
│   │   └── resolvers.py         # require_workspace_role, require_organization_role, workspaces_for
│   ├── accounts/
│   │   └── registration.py      # register_user, ensure_personal_workspace (I1)
│   ├── organizations/
│   │   ├── organization.py      # create, rename
│   │   └── membership.py        # add / change / remove members; workspace sync (I2, I4)
│   └── workspaces/
│       ├── workspace.py         # create (creator becomes owner, I5), rename
│       ├── membership.py        # add / change / remove members (I3, I6)
│       └── recovery.py          # operator-only ownership recovery
│   # later, with their first feature: statement_analysis/, documents/,
│   #   stock_research/, portfolio_analysis/
├── api/                         # shared DRF plumbing for every endpoint
│   ├── exceptions.py            # error envelope; maps ConflictError → 409
│   ├── pagination.py            # StandardPagination
│   └── permissions.py           # shared DRF permission classes, when one is needed
├── apps/                        # Django integration: models, migrations, admin, endpoints
│   ├── core/                    # models.py (PublicModel), admin.py (ReadOnlyModelAdmin),
│   │                            #   request IDs, health
│   ├── accounts/                # models, admin, backends.py
│   │   └── api/                 # authentication, throttles, serializers, views, urls
│   ├── organizations/           # models, admin, migrations/
│   │   └── api/                 # serializers, views, urls
│   ├── workspaces/              # models, admin, migrations/ (incl. personal-workspace backfill)
│   │   └── api/                 # scoping.py (WorkspaceScopedMixin), serializers, views, urls
│   └── audit/                   # models (AuditEvent.record), admin, migrations/
├── config/
│   ├── settings/base.py         # INSTALLED_APPS: + organizations, workspaces, audit
│   └── api_v1.py                # includes the accounts, organizations and workspaces urls
├── pyproject.toml               # `services` added to Ruff first-party and coverage sources
└── tests/
    ├── services/                # use-case tests (invariants, concurrency, query budgets)
    ├── organizations/           # organization API tests
    ├── workspaces/              # workspace API tests: role matrix and isolation
    ├── audit/
    └── test_architecture.py     # domain imports no `services`; services import no DRF
```

Layout rule: **core logic in `services/<capability>/`, every endpoint in
`apps/<app>/api/`, and shared DRF plumbing in `backend/api/`**. Models, migrations and admin
stay at the app's top level. The `recover_workspace_owner` management command is not
scaffolded, because an empty command module would break `manage.py`. It lands with its code
in 1c.

## 7. Clean-code rules for this work

1. **Views are thin.** A view parses input with a serializer, calls one use case and returns a
   serializer of the result. No business rules or queries beyond `get_queryset` belong in a
   view.
2. **Use cases are functions, not classes.** They take keyword-only arguments and are fully
   typed (mypy strict). They raise `Http404`, `PermissionDenied` or `ConflictError`, never DRF
   exceptions. Multi-write use cases carry `@transaction.atomic`, so they are also atomic when
   called from management commands and tests, not only inside `ATOMIC_REQUESTS`.
3. **The ORM is the repository.** Use cases use querysets directly. A repository layer over
   the ORM would duplicate it without isolating anything, because there is one database. This
   refines DOMAIN_BOUNDARIES §1, which mentions repositories, and that document is updated to
   match.
4. **Constraints live in the database.** Uniqueness, the workspace owner-kind CHECK and the
   enum CHECKs are database constraints. Python checks only what the database cannot express
   (I1–I4).
5. **No speculative code:** no unused fields, statuses, settings, hooks, signals, base classes
   with one subclass, or permission classes per object. Django signals are not used; use cases
   call `AuditEvent.record()` explicitly, so the flow is readable top to bottom.
6. **No new dependencies.** Everything uses Django, DRF and pytest-django, which are already
   locked.
7. **Audit without financial values.** Events are `auth.*`, `organization.*`, `workspace.*`
   and `membership.*`, with the actor, target `public_id`, `request_id` (from the existing
   request context) and non-financial metadata only.

## 8. Implementation sequence

Each item is one pull request with green CI on PostgreSQL. The size is a target for non-test
code, to keep the work small.

| PR | Scope | Acceptance | Target size |
|---|---|---|---|
| **0. Decide** | ADR-0008 *Organizations and workspace tenancy* (this design); update DATA_MODEL §2–4, DOMAIN_BOUNDARIES §2–3 (`organizations` moves from Future to Phase 1, `workspaces` becomes its own app per A7) and PRODUCT_SCOPE FR-004 ("business workspace" becomes "organization workspace") | Reviewed and accepted; records the §10 decisions | docs only |
| **1a. Tenancy models** — *implemented 2026-10-27; 170 tests green on SQLite and PostgreSQL* | `PublicModel`; `Organization`, `OrganizationMembership`, `Workspace`, `WorkspaceMembership` and their migrations; a data migration giving every existing user a personal workspace and owner membership; `services/access/resolvers.py`, `services/errors.py`; read-only admin for the four models; user deletion disabled in the admin | Constraint tests (one owner kind, unique personal workspace, unique memberships, CHECKs) pass on PostgreSQL; the data migration is tested forwards, including re-running it on users who already have a workspace; `require_workspace_role` returns 404 for non-members and 403 for a role that is too low, using one query; the admin cannot delete or edit tenancy rows | ~170 lines |
| **1b. Authentication and audit** — *implemented 2026-10-27; 194 tests green on SQLite and PostgreSQL* | ADR-0007 in code: `EmailBackend`, an email non-blank CHECK, an `authenticate_header` subclass (`401`), login throttles (IP and email), `SESSION_COOKIE_AGE` and `SESSION_SAVE_EVERY_REQUEST`; auth endpoints; `register_user` and `ensure_personal_workspace` on sign-in (I1); the `audit` app | Registering creates exactly one personal workspace; a `createsuperuser` account gets one on first sign-in; the sixth failed login per minute gets `429`; unauthenticated calls get `401` with `WWW-Authenticate: Session`; `test_anonymous_requests_are_rejected_by_default` is updated; login events are recorded without passwords | ~180 lines |
| **1c. Workspace API** | `WorkspaceScopedMixin`; workspace and workspace-member endpoints; `services/workspaces/` (I3, I5, I6); the `recover_workspace_owner` command | Full role matrix; non-member gets `404`; viewer gets `403` on writes; creating a workspace makes its creator the owner, and a failure part-way leaves nothing behind; last owner cannot leave or be demoted, including under concurrency; personal workspace rejects members; inactive users cannot be added; recovery refuses every unsafe case and always writes its audit event; query budgets in §4 hold | ~210 lines |
| **1d. Organization API** | Organization and organization-member endpoints; `services/organizations/` (I2, I4) | Removing a member from the organization removes their workspace memberships in it, and is blocked if they are the last owner of one; last admin is protected; the organization admin cannot read a workspace they are not a member of | ~150 lines |
| **Steps 2–8** | As in the [MVP plan](MVP_IMPLEMENTATION_PLAN.md). Every new tenant model carries a `workspace` FK, and every tenant view inherits `WorkspaceScopedMixin` | The isolation tests below are repeated for each new resource | — |

### Security tests that must exist by the end of 1d

From the proposal, written as parametrized tests rather than one-off cases:

- A user in organization A cannot list, read or modify organization B, its members or its workspaces (`404`).
- A member of an organization cannot access an organization workspace they are not a member of (`404`), and neither can an organization admin.
- A viewer cannot rename a workspace or manage its members (`403`).
- A user cannot read another user's personal workspace by guessing its `public_id` (`404`).
- Every endpoint answers `401` for an anonymous caller.
- In step 4 and later: a document from another workspace cannot be downloaded by its ID (`404`), because the scoped queryset never finds it.

## 9. Deferred work and how it plugs in

| Feature | When | Where it plugs in |
|---|---|---|
| Teams | When organizations ask to manage access for a group | Teams **manage memberships; they do not change the access model**. `Team` and `TeamMembership` live in the organization. Adding a team to a workspace with a role creates ordinary `WorkspaceMembership` rows for its members, marked with the team that granted them, and team membership changes add or remove those rows in the same transaction. `require_workspace_role`, the mixin and every view stay unchanged, and the access check is still one query. The rule for a user who has both a direct and a team-granted role is decided when teams are designed |
| Email invitations | When email delivery is configured | An `Invitation(email, organization, role, token hash, expires_at)`; the add-by-email endpoint becomes "invite" |
| Reviewer role | Phase 2 (PDF review) | A new rank between viewer and editor in `_RANK`, plus a review permission on review endpoints |
| Organization-level policies or settings | When the first policy exists | A typed model or column, not a generic JSON blob |
| Workspace and organization deletion | Step 8 | A deletion use case with the A8 grace period; RESTRICT and CASCADE behaviour as DATA_MODEL principle 4 |
| Background jobs | Phase 2 | Jobs store the workspace and the initiating user, and call `require_workspace_role` again when they run |

## 10. Decisions (2026-10-27)

These are decided by the maintainer and are to be recorded in ADR-0008 (PR 0).

| # | Question | Decision |
|---|---|---|
| Q1 | Who may create an organization? | **Any authenticated user**, who becomes its admin. Subscription limits or organization verification can be added later without changing the model |
| Q2 | Who may create workspaces in an organization? | **Any member of the organization**, who becomes its owner in the same transaction (I5). Deactivated accounts cannot act (I6) |
| Q3 | Can an organization admin take over a workspace whose owners have all left? | **No automatic takeover.** Removing or leaving as the last owner is blocked until ownership is transferred (I2, I3). Exceptional cases, such as every owner being deactivated, go through the audited, operator-only [recovery command](#ownership-recovery-exceptional-cases-only). Organization admins never gain access to workspace data on their own |
| Q4 | Can a personal workspace be shared? | **No, for the initial implementation.** Personal workspaces stay outside organizations and private to their owner. Collaboration happens in organization workspaces |
| Q5 | Should teams be deferred? | **Yes.** Direct workspace membership comes first. Teams later become a way to manage memberships, without redesigning the access model (§9) |

## 11. Documents to update with this work

- New: `docs/decisions/ADR-0008-organizations-and-workspace-tenancy.md` (PR 0).
- [DATA_MODEL](../data/DATA_MODEL.md): §2 entity table (apps `organizations` and `workspaces`; Organization moves to MVP), §3 diagram, §4.2 (no `kind`; the owner-kind CHECK), §4.3 (renamed `WorkspaceMembership`), new organization tables.
- [DOMAIN_BOUNDARIES](../architecture/DOMAIN_BOUNDARIES.md): module map and tables; the §1 wording on repositories.
- [PRODUCT_SCOPE](../product/PRODUCT_SCOPE.md): FR-003 to FR-005 and acceptance criterion 2 refer to organization workspaces.
- [API_CONVENTIONS](../api/API_CONVENTIONS.md): the nested resource rule and the `409 conflict` code.
- [MVP_IMPLEMENTATION_PLAN](MVP_IMPLEMENTATION_PLAN.md): step 1 points to this plan.
- `CHANGELOG.md`, in each PR.
