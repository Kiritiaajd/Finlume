# Contributing to Finlume

Thank you for helping build Finlume. This guide covers how to propose changes;
the detailed engineering conventions live in [`docs/`](docs/).

## Ground rules

- **Never commit real financial data, credentials or personal information.**
  That includes code, tests, fixtures, screenshots, issues and pull requests. Use
  clearly fictional figures.
- **Calculations must be deterministic and explained.** Financial arithmetic
  lives in `backend/domain/`, uses `Decimal`, and changes to it follow
  [the calculation conventions](docs/data/FINANCIAL_CALCULATION_CONVENTIONS.md).
- **AI never produces financial numbers.** Any future AI feature only explains
  results the engine has already calculated.
- Be respectful. Participation is governed by the [Code of Conduct](CODE_OF_CONDUCT.md).
- Report security issues privately, as described in [SECURITY.md](SECURITY.md).

## Before you start

1. Check existing issues and the [product scope](docs/product/PRODUCT_SCOPE.md).
   Work outside the current phase is welcome as discussion. Open an issue
   before building it.
2. For a change to architecture, data model or a public API, open an issue
   first. Material decisions are recorded as an
   [ADR](docs/decisions/README.md).

## Development setup

Follow [docs/development/LOCAL_SETUP.md](docs/development/LOCAL_SETUP.md). In
short (PowerShell; use `source .venv/bin/activate` on macOS/Linux):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
cd backend
python -m pip install --require-hashes -r requirements/dev.txt
python manage.py migrate
python -m pytest
```

## Making a change

The full workflow is in
[docs/development/DEVELOPMENT_WORKFLOW.md](docs/development/DEVELOPMENT_WORKFLOW.md).

1. Branch from `main`, using a short-lived branch named `feat/…`, `fix/…`,
   `docs/…` or `chore/…`.
2. Write tests with your change. Calculation changes need hand-verified
   expected values and edge cases: missing inputs, zero, negative values and
   rounding.
3. Run the quality gates locally: `.\scripts\check.ps1` or `./scripts/check.sh`.
   See [QUALITY_GATES.md](docs/development/QUALITY_GATES.md).
4. Use [Conventional Commits](https://www.conventionalcommits.org/), for
   example `feat(analysis): add interest coverage ratio`.
5. Update the docs and the **Unreleased** section of [CHANGELOG.md](CHANGELOG.md).
6. Open a pull request and complete the template. CI must pass and a
   maintainer must approve before merge (squash merge).

## Licensing of contributions

Finlume is released under the [MIT License](LICENSE). By submitting a
contribution you agree that it is licensed under the same terms
(inbound = outbound). No contributor licence agreement is required.
