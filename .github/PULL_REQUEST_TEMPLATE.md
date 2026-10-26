## Summary

<!-- What does this change do, and why? Link the issue it resolves (e.g. "Closes #12"). -->

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Financial calculation or methodology change
- [ ] Documentation
- [ ] Refactor / maintenance
- [ ] Dependency update

## How was this verified?

<!-- Commands run and their results. "Tests pass" is not enough on its own: say which. -->

## Checklist

- [ ] `scripts/check.ps1` or `scripts/check.sh` passes locally.
- [ ] Tests cover the new behaviour, including edge cases (missing values, zero, negative, rounding).
- [ ] Migrations are included for model changes and reviewed for data safety.
- [ ] Docs updated where behaviour, API, configuration or architecture changed.
- [ ] `CHANGELOG.md` updated under **Unreleased** for user-visible changes.
- [ ] No secrets, credentials, real personal data or real financial records anywhere in the change (code, tests, fixtures, screenshots).

### For calculation changes only

- [ ] `ENGINE_VERSION` bumped and the change recorded in `CHANGELOG.md`.
- [ ] Methodology text updated and expected values verified by hand or against an independent source.
- [ ] `docs/data/FINANCIAL_CALCULATION_CONVENTIONS.md` updated if a convention changed.
