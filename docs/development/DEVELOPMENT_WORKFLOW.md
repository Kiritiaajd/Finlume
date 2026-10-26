# Development workflow

## Branching

Finlume uses trunk-based development on `main`.

- `main` is always releasable. Nobody pushes directly; every change arrives through a pull request.
- Work on short-lived branches cut from `main` and named by type:

  | Prefix | Use |
  |--------|-----|
  | `feat/` | New capability (`feat/statement-csv-import`) |
  | `fix/` | Bug fix (`fix/current-ratio-zero-liabilities`) |
  | `docs/` | Documentation only |
  | `chore/` | Tooling, dependencies, CI, refactors with no behaviour change |

- Keep branches small and merge within days. Rebase on `main` rather than merging `main` into the branch.

## Commits

Use [Conventional Commits](https://www.conventionalcommits.org/):

```text
feat(analysis): add interest coverage ratio
fix(validation): ignore missing equity in balance sheet check
docs(api): document pagination limits
chore(deps): bump Django to 5.2.19
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `chore`, `ci`. Mark breaking API or calculation changes with `!` (`feat(api)!: ...`) and a `BREAKING CHANGE:` footer.

## Pull requests

1. Open a PR against `main` and fill in the [template](../../.github/PULL_REQUEST_TEMPLATE.md).
2. CI must be green (see [QUALITY_GATES.md](QUALITY_GATES.md)).
3. At least one maintainer approves. A change to a financial calculation also needs its expected values verified independently; see the template checklist.
4. **Squash merge**, so the squash commit title is a Conventional Commit.
5. Update [`CHANGELOG.md`](../../CHANGELOG.md) under **Unreleased** for user-visible changes.

### Branch protection (one-time GitHub setup)

Configure the following on GitHub under **Settings → Branches → `main`**:
- require a pull request with one approval;
- require the `Backend (...)`, `Dependency audit` and `Lock files match pyproject.toml` checks to pass;
- require branches to be up to date;
- disallow force pushes and deletion.

This is a repository setting, so it cannot be committed to the repository.

## Making a change

1. Read the relevant docs: [DOMAIN_BOUNDARIES](../architecture/DOMAIN_BOUNDARIES.md) for where code belongs, and [FINANCIAL_CALCULATION_CONVENTIONS](../data/FINANCIAL_CALCULATION_CONVENTIONS.md) for calculations.
2. Write or update tests first for domain logic. Calculations are pure functions and easy to test in isolation.
3. Run `scripts/check.ps1` (Windows) or `scripts/check.sh` before pushing.
4. Record significant architectural choices as an ADR ([docs/decisions](../decisions/README.md)).

## Database migrations

- Generate with `python manage.py makemigrations <app>` and **read the generated file** before committing. Check it for unintended drops, renames detected as drop-and-add, and non-null columns without defaults on populated tables.
- Each migration belongs to the PR that changes the model, and CI fails if models and migrations disagree (`makemigrations --check --dry-run`).
- Separate schema changes from data migrations, and give each data migration a reverse operation, or document why it cannot have one.
- Run `migrate` only against your own local Finlume database (the Compose container, a dedicated database on your own server, or an opted-in SQLite file). Check the target first with the read-only `python manage.py dbstatus`. **Never run migrations from a development machine against a shared, production or unknown database.**
- Never edit a migration that has been merged; add a new one.
- Never reset or drop databases holding anyone else's data.

## Secrets and financial data

- Secrets come only from environment variables. `.env` is git-ignored; [`.env.example`](../../.env.example) contains placeholders only.
- Tests, fixtures, screenshots, issues and PRs use **fictional figures only**. Never use real bank statements, real personal records or customer data, even "anonymised".
- Publicly listed companies' published statements may be used as test data only if the source and licence are documented next to the fixture.
- Do not log financial values, document contents or credentials (see [ERROR_HANDLING_AND_OBSERVABILITY](../architecture/ERROR_HANDLING_AND_OBSERVABILITY.md)).
- If a secret is committed by mistake, treat it as compromised and rotate it. Deleting it from history alone is not enough. Then tell the maintainers.

## Releases

The project uses Semantic Versioning, and [`CHANGELOG.md`](../../CHANGELOG.md) follows Keep a Changelog. The calculation engine has its own `ENGINE_VERSION` (`backend/domain/calculations/version.py`), which is bumped whenever any calculated output could change ([ADR-0003](../decisions/ADR-0003-deterministic-calculation-engine.md)).
