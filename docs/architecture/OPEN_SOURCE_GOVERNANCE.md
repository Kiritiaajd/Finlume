# Open-Source Governance

How Finlume is licensed, maintained, decided on, released and kept safe as a
public open-source project.

Related: [CONTRIBUTING.md](../../CONTRIBUTING.md), [CODE_OF_CONDUCT.md](../../CODE_OF_CONDUCT.md), [SECURITY.md](../../SECURITY.md), [CHANGELOG.md](../../CHANGELOG.md), [DEVELOPMENT_WORKFLOW.md](../development/DEVELOPMENT_WORKFLOW.md).

## 1. License

- Finlume is licensed under the **MIT License** ([LICENSE](../../LICENSE), © 2026 Kiriti Aajad). The existing license is retained unchanged.
- Changing the license would need agreement from all copyright holders whose contributions are affected. It is not planned.

## 2. Contributions

| Topic | Policy | Status |
|---|---|---|
| Inbound licensing | **Inbound = outbound.** Contributions are accepted under the project's MIT license, as GitHub's Terms of Service state for contributions to a licensed repository. | Decided |
| Contributor License Agreement | **None.** No CLA is required. | Decided |
| Developer Certificate of Origin | Requiring `Signed-off-by` (DCO, `git commit -s`) would add a lightweight provenance record. | **Open:** not required yet; decide before accepting significant external contributions |
| Contribution process | Issues first for non-trivial changes, then pull requests against `main` with green CI. See [CONTRIBUTING.md](../../CONTRIBUTING.md) and [DEVELOPMENT_WORKFLOW.md](../development/DEVELOPMENT_WORKFLOW.md). | Decided |
| Code of conduct | [CODE_OF_CONDUCT.md](../../CODE_OF_CONDUCT.md) applies to all project spaces. The enforcement contact is **Open** (see §8). | Decided (contact Open) |

## 3. Maintainers and roles

- **Current model:** a single maintainer, **@Kiritiaajd** (Kiriti Aajad), who owns the repository, merges pull requests, cuts releases and handles security reports.
- **Path to more maintainers:** a contributor with a sustained record of high-quality reviews and merged contributions can be invited as a maintainer by the existing maintainers. Maintainers receive merge rights. Releases and security-advisory access are granted separately.
- **Planned roles as the project grows:**
  - *Maintainer*: merge, triage and release.
  - *Reviewer*: approving reviews in an area, e.g. the calculation engine or the frontend.
  - *Domain reviewer*: someone with accounting or finance expertise who signs off methodology changes.
- **CODEOWNERS:** once there is more than one maintainer, `.github/CODEOWNERS` will require a domain reviewer on `backend/domain/` and on `docs/data/FINANCIAL_CALCULATION_CONVENTIONS.md`.

## 4. Decision making

- **Everyday decisions** happen in issues and pull-request reviews. The maintainer decides when consensus is unclear.
- **Architecturally significant decisions** are recorded as **ADRs** in [`docs/decisions/`](../decisions/). These are decisions that are hard to reverse, affect several modules, or change a security, privacy or data-correctness property. An ADR is proposed in a pull request, discussed there, and merged as `Accepted`, or not merged. A superseded ADR stays in the repository and is marked `Superseded by ADR-NNNN`. The index lives in [ARCHITECTURE_DECISIONS.md](ARCHITECTURE_DECISIONS.md).
- **Scope changes** (new user groups, phases or non-goals) update [PRODUCT_SCOPE.md](../product/PRODUCT_SCOPE.md) in a reviewed pull request.
- **Calculation methodology changes** require hand-verified test expectations, an `ENGINE_VERSION` bump and a changelog entry (§5).

## 5. Releases and versioning

| Item | Policy |
|---|---|
| Project version | **Semantic Versioning** (`MAJOR.MINOR.PATCH`). During `0.x`, minor versions may contain breaking changes, which are always called out in the changelog. The first tagged release will be `0.1.0` at the end of Phase 1 (MVP). |
| API version | URL-versioned (`/api/v1/`). Breaking changes go into a new version served side by side during a documented deprecation window ([API_CONVENTIONS.md](../api/API_CONVENTIONS.md)). |
| Calculation engine version | `ENGINE_VERSION` in `backend/domain/calculations/version.py` (currently `0.1.0`), versioned **independently** of the project. It is bumped whenever any calculated value, issue or methodology text could change for the same input, and recorded with every saved analysis so historical results stay explainable. |
| Changelog | [CHANGELOG.md](../../CHANGELOG.md) follows **Keep a Changelog**. Every user-visible change and every `ENGINE_VERSION` bump is listed under *Unreleased* until a release is cut. |
| Release process (planned) | All CI gates green on `main` → `manage.py check --deploy` reviewed → changelog section dated → annotated git tag `vX.Y.Z` → GitHub release notes copied from the changelog. |
| Supported versions | Only the latest release receives security fixes until the project reaches `1.0`. |

## 6. Security disclosure

- Vulnerabilities are reported **privately** through GitHub's private vulnerability reporting (*Security → Report a vulnerability*). The issue-template configuration already links to it, and [SECURITY.md](../../SECURITY.md) describes the process.
- **Maintainer action required:** enable *Private vulnerability reporting* in the repository settings (*Settings → Code security*). Until it is enabled, that link does not accept reports. Enabling Dependabot alerts and secret scanning is also recommended.
- A dedicated security contact email address is **Open**.
- Fixes are released, then disclosed through a GitHub Security Advisory that credits the reporter if they wish.

## 7. Dependency policy

1. **License compatibility.** Runtime dependencies must use licenses compatible with MIT distribution (MIT, BSD, Apache-2.0, ISC, PSF, LGPL used as a library). **Avoid GPL and AGPL dependencies in the core runtime.** A copyleft dependency in an optional, separately installed integration needs an ADR.
2. **Minimalism.** Add a dependency only when it removes meaningful risk or effort. Example: Finlume reads environment variables with a small typed helper instead of adding a configuration library.
3. **Maintenance.** Prefer actively maintained, widely used packages. Prefer an LTS line for frameworks (Django 5.2 LTS).
4. **Reproducibility.** `backend/pyproject.toml` declares dependencies; the hash-pinned `backend/requirements/*.txt` lock files are generated with `uv pip compile` and never edited by hand ([ADR-0004](../decisions/ADR-0004-dependency-management.md)). CI fails if the locks drift from `pyproject.toml`.
5. **Vulnerability response.** `pip-audit` runs in CI. A runtime advisory blocks merging until the dependency is upgraded or the advisory is documented as not applicable. Example: DRF moved from 3.16.1 to 3.18.3 for that reason. The development-only `filelock` advisory that affects Python 3.10 alone is a known exception, pending the decision to raise the Python floor to 3.12.
6. **Frontend packages** (once introduced) follow the same rules, with a committed lock file and `npm audit` (or an equivalent) in CI.

## 8. Data in the repository

- **No real financial data**, ever. That covers fixtures, test files, sample CSVs, screenshots, issues and pull requests. Use fictional companies and figures.
- **No secrets.** `.env` files, keys and credentials are git-ignored, and `.env.example` holds placeholders only.
- If real data or a secret is committed by mistake, treat it as an incident:
  1. Rotate the secret.
  2. Remove the data from history (e.g. `git filter-repo`) with maintainer coordination.
  3. Ask GitHub support to purge cached views if necessary.
- Issue templates remind reporters not to share real figures or personal information.

## 9. Name and trademark

"Finlume" is the project's name. Forks are welcome under the MIT license.
Forks that are distributed or hosted publicly should use a different name and
logo, so users are not misled about which software and which operator handles
their financial data. No trademark is registered at this time.

## 10. Financial-advice disclaimer

Finlume is software for financial analysis and education. It **does not
provide investment, tax, accounting or legal advice**, does not guarantee
returns, and does not replace a qualified professional. Calculations are
deterministic and documented, but results are only as accurate as the input
data. AI-generated explanations (a future, optional feature) are labelled as
generated and are grounded in stored calculation results. This disclaimer
must appear in the README and, once a user interface exists, in the
application itself.

## 11. Open governance decisions

| Decision | Owner |
|---|---|
| Require DCO sign-off? | Maintainer |
| Security contact email and Code of Conduct enforcement contact | Maintainer |
| Enable private vulnerability reporting, Dependabot alerts, secret scanning and branch protection on `main` | Maintainer (repository settings) |
| Hosting model: self-host only, or also an official hosted instance (which brings additional privacy-policy and terms obligations) | Maintainer |
| Raise the Python floor from 3.10 (end of life October 2026) to 3.12 | Maintainer |
