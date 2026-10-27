# Finlume — Product Scope

| | |
|---|---|
| Status | Draft for the MVP (Phase 1). Phase 0 (foundation) is in progress. |
| Owner | Project maintainers |
| Related | [System overview](../architecture/SYSTEM_OVERVIEW.md) · [Data model](../data/DATA_MODEL.md) · [Calculation conventions](../data/FINANCIAL_CALCULATION_CONVENTIONS.md) |

Requirement IDs (`FR-nnn`, `NFR-nnn`) are stable. A requirement that is dropped is
marked **Withdrawn**; its ID is never reused.

Each item in this document has one of three statuses:

- **Implemented**: exists in the repository today.
- **MVP**: designed and committed for Phase 1, but not built yet.
- **Future**: a later phase. It is not built, and its design may change.

---

## 1. Vision and objectives

Finlume is an open-source financial intelligence platform. It turns financial data into
verifiable insight for individuals, businesses and retail investors.

Objectives:

1. **Correctness first.** Every number Finlume shows can be traced back to its inputs and the method used to calculate it. Calculations are deterministic, versioned and tested.
2. **Explainability.** Results carry their methodology, inputs and warnings. Future AI explanations will only restate verified, stored results. AI never performs the arithmetic.
3. **Privacy and control.** Users own their data. Finlume can be self-hosted and run without third-party services.
4. **Accessibility.** Analysis that normally needs a spreadsheet expert becomes usable by non-specialists.
5. **Open collaboration.** The calculation engine is transparent, documented and open to review.

Finlume supports understanding and decision-making. It does not give investment, tax or
legal advice, and it does not guarantee outcomes.

## 2. Intended user groups

| # | Group | Primary needs | First served in |
|---|-------|---------------|-----------------|
| U1 | Salaried individuals | Income, expenses, savings, cash flow | Phase 4 |
| U2 | Self-employed people and freelancers | Business-like income tracking, irregular cash flow, simple statements | Phase 1 (statements), Phase 4 (transactions) |
| U3 | SMEs and small/medium businesses | Financial statement analysis, ratios, period comparison | **Phase 1** |
| U4 | Retail business owners and shopkeepers | Simple statements, margins, liquidity; minimal accounting knowledge | **Phase 1** |
| U5 | Retail investors and people researching listed companies | Company fundamentals, ratios, peer comparison, portfolios | **Phase 1** (manual company data), Phase 5 (market data, portfolios) |

## 3. Core use cases

| ID | Use case | Groups | Phase |
|----|----------|--------|-------|
| UC-01 | Enter a company's income statement, balance sheet and cash-flow figures for a period, by hand | U2–U5 | MVP |
| UC-02 | Upload a CSV of statement figures, map its rows to Finlume line items and review the result | U2–U5 | MVP |
| UC-03 | See validation warnings (for example, a balance sheet that does not balance) before trusting results | U2–U5 | MVP |
| UC-04 | Run an analysis and see ratios with their methodology, inputs and warnings | U2–U5 | MVP |
| UC-05 | Save an analysis and come back to it later with identical results | U2–U5 | MVP |
| UC-06 | View a dashboard/report for an entity: metrics, statement figures, warnings | U2–U5 | MVP |
| UC-07 | Correct (restate) a statement without losing the earlier version or analyses based on it | U2–U5 | MVP |
| UC-08 | Upload an annual report PDF and review extracted figures before they are used | U3, U5 | Future (Phase 2) |
| UC-09 | Ask for a plain-language explanation of results, grounded in stored values | All | Future (Phase 3) |
| UC-10 | Import bank or card transactions from CSV/Excel and categorise spending | U1, U2 | Future (Phase 4) |
| UC-11 | Research a listed company using provider data and compare it with peers | U5 | Future (Phase 5) |
| UC-12 | Track a portfolio's allocation, returns and risk | U5 | Future (Phase 5) |
| UC-13 | Use Finlume from a mobile app | All | Future (after the v1 API stabilises) |

## 4. Capabilities by domain

The domains are separated where their data models, permissions or rules differ (see
[Domain boundaries](../architecture/DOMAIN_BOUNDARIES.md)).

| Domain | Capabilities | Status |
|--------|--------------|--------|
| **Platform** | Accounts, workspaces, memberships and roles, audit trail, health endpoint, versioned API | Health endpoint and custom user model: Implemented. Workspaces, roles and audit: MVP |
| **Financial statements** (business finance and company research) | Manual entry, CSV import, line-item mapping, normalisation, validation, restatements | MVP |
| **Analysis engine** | Deterministic ratios, validation checks, engine versioning, saved analysis runs | Engine core: Implemented. Persistence and API: MVP |
| **Reporting** | Dashboards, charts, period comparison, reports | Single-period dashboard/report: MVP. Multi-period comparison: Future |
| **Documents** | Private storage, source provenance, PDF/annual-report extraction with human review | Private storage class: Implemented. CSV source records: MVP. PDF: Future (Phase 2) |
| **AI explanations** | Grounded explanations of stored results, pluggable providers including local models | Future (Phase 3) |
| **Personal finance** | Accounts, transactions, categories, budgets, personal cash flow | Future (Phase 4) |
| **Investments** | Securities, market data, valuation metrics, peer comparison, portfolio analytics | Future (Phase 5) |
| **Clients** | Web app (React + TypeScript + Vite); mobile app (React Native + Expo) | Web: MVP. Mobile: Future |

## 5. MVP scope and future scope

### 5.1 MVP (Phase 1)

The MVP proves one complete, demonstrable workflow:

> **Manual or CSV financial statement input → validation → deterministic financial
> calculations → saved analysis → dashboard/report**

In scope:

- Users register and sign in to the web app (session authentication).
- A personal workspace is created for each user. Users can create business workspaces and invite members as owner, editor or viewer.
- Reporting entities (a business or a company being researched) inside a workspace.
- Manual entry and CSV upload of income statement, balance sheet and cash-flow figures for one period. Each statement uses one currency and one reporting scale.
- Mapping of input rows to the canonical line-item taxonomy, with a review step.
- Validation: sign conventions, the balance-sheet identity and the gross-profit subtotal.
- The seven MVP ratios defined in [Calculation conventions](../data/FINANCIAL_CALCULATION_CONVENTIONS.md).
- Saved, immutable analysis runs that record the engine version and an input fingerprint.
- A web dashboard/report for one entity and period, with ECharts visualisations of the results.
- Restatement: a correction creates a new statement version and keeps the earlier one.
- An audit trail of create, update, delete and analysis actions.

### 5.2 Future scope (indicative order, not committed)

| Phase | Theme | Highlights |
|-------|-------|------------|
| 2 | Document ingestion | Private uploads, PDF/annual-report extraction, mandatory human review, background jobs (Celery + Redis introduced here) |
| 3 | AI-assisted explanations | Optional and off by default; provider-pluggable with a local-model option; explanations cite stored metric results |
| 4 | Personal finance | Accounts, CSV/Excel transaction import, categories, budgets, cash flow |
| 5 | Investments and market data | Provider-backed company data, valuation metrics, peer comparison, portfolio analytics |
| — | Mobile app | Starts after the v1 API stabilises following the MVP |
| — | Multi-period analysis | Trends, growth rates, average-balance ratios (needs two or more periods) |
| — | Bank integrations | Unscheduled; needs a separate security and legal review |

## 6. Non-goals for the initial release

The MVP will **not**:

- Ingest PDFs or extract figures with OCR or AI.
- Generate AI explanations or call any LLM.
- Connect to banks, brokers or payment providers.
- Fetch live or delayed market data, or subscribe to paid data feeds.
- Convert currencies, or combine figures in different currencies.
- Provide portfolio analytics or valuation models.
- Ship a mobile app.
- Act as a bookkeeping or accounting system (no double-entry ledger, invoicing, payroll or tax filing).
- Give investment, tax or legal advice, or recommend securities.
- Offer a hosted multi-tenant SaaS. The MVP targets self-hosting and local use (see §9).

## 7. Functional requirements

### Accounts and workspaces

| ID | Requirement | Phase |
|----|-------------|-------|
| FR-001 | Users can register, sign in and sign out with a username/email and password. | MVP |
| FR-002 | Email addresses are unique without regard to case. | Implemented (model constraint) |
| FR-003 | Each user has a personal workspace, created automatically. | MVP |
| FR-004 | Users can create business workspaces and invite existing users as owner, editor or viewer. | MVP |
| FR-005 | Users can see and change only the data of workspaces they belong to. Viewers can read but not change. | MVP |
| FR-006 | The API identifies users and records by opaque UUIDs, never by sequential database IDs. | Implemented (users); MVP (all records) |

### Financial statement input

| ID | Requirement | Phase |
|----|-------------|-------|
| FR-010 | Users can create reporting entities within a workspace. | MVP |
| FR-011 | Users can enter income statement, balance sheet and cash-flow figures by hand for a reporting period. | MVP |
| FR-012 | Each statement records its currency (ISO 4217), reporting scale (units, thousands, lakhs, millions, crores, billions), period start and end, and period type. | MVP |
| FR-013 | Users can upload a CSV file of statement figures. The file is stored privately and fingerprinted with SHA-256. | MVP |
| FR-014 | CSV rows are mapped to canonical line items. Users review and confirm the mapping before facts are created. | MVP |
| FR-015 | Inputs are rejected when they are not valid decimal numbers (including NaN or infinity), have invalid dates (start after end), have a malformed currency code, or are missing a required column. | Domain checks Implemented; API MVP |
| FR-016 | Each normalised figure keeps a link to the raw value, the statement version and the source it came from. | MVP |
| FR-017 | Correcting a statement creates a new version. The previous version and analyses based on it remain readable. | MVP |

### Validation

| ID | Requirement | Phase |
|----|-------------|-------|
| FR-020 | The system flags values that break the sign convention. | Implemented (domain) |
| FR-021 | The system flags when total assets differ from total liabilities plus total equity by more than 0.1 % of total assets. | Implemented (domain) |
| FR-022 | The system flags when gross profit differs from revenue minus cost of revenue by more than 0.1 % of revenue. | Implemented (domain) |
| FR-023 | Validation reports issues with a stable code, a severity and the line items involved. It never changes data. | Implemented (domain) |

### Calculation and analysis

| ID | Requirement | Phase |
|----|-------------|-------|
| FR-030 | The system computes gross margin, operating margin, net margin, current ratio, debt to equity, return on equity and return on assets. | Implemented (domain) |
| FR-031 | A missing input or a zero denominator produces "not computable" with an explanatory issue. A missing input is never treated as zero. | Implemented (domain) |
| FR-032 | Every metric result carries its methodology text and the input values used. | Implemented (domain) |
| FR-033 | Every analysis run records the engine version, an input fingerprint, its creator and a timestamp. A completed run is immutable. | MVP |
| FR-034 | Re-running an analysis on the same inputs with the same engine version gives identical results. | Implemented (domain); MVP (persisted) |

### Reports and dashboards

| ID | Requirement | Phase |
|----|-------------|-------|
| FR-040 | Users can save an analysis with a title and notes, and reopen it later. | MVP |
| FR-041 | The web dashboard shows the metrics, statement figures, validation issues and engine version for an entity and period. | MVP |
| FR-042 | Metrics appear as percentages or ratios with display rounding. Stored values keep full stored precision. | MVP |
| FR-043 | Charts show only calculated, stored values. They never estimate or interpolate missing data. | MVP |

### API and platform

| ID | Requirement | Phase |
|----|-------------|-------|
| FR-050 | All client features use the versioned REST API under `/api/v1/`. Web and mobile clients share it. | Implemented (routing) |
| FR-051 | A public health endpoint reports application and database readiness without exposing internal details. | Implemented |
| FR-052 | API errors use one JSON envelope with a stable code, a safe message and a request ID. | Implemented |
| FR-053 | Security-relevant and data-changing actions are recorded as audit events. | MVP |
| FR-054 | Workspace owners can export their workspace's statements and analyses as CSV/JSON. | MVP |
| FR-055 | Workspace owners can delete a workspace and all of its financial data (see [Data lifecycle](../data/DATA_LIFECYCLE_AND_RETENTION.md)). | MVP |

## 8. Non-functional requirements

| ID | Category | Requirement | Status |
|----|----------|-------------|--------|
| NFR-001 | Correctness | Monetary values and calculations use `Decimal`. Floating point is never used for money. Floats passed into the domain are rejected. | Implemented |
| NFR-002 | Correctness | Calculations run in an explicit decimal context (34 digits of precision, half-even rounding). Results are stored to 6 decimal places. | Implemented |
| NFR-003 | Correctness | Each calculation change that alters output bumps `ENGINE_VERSION` and is recorded in the changelog. | Implemented (policy and constant) |
| NFR-004 | Correctness | The domain layer has no framework dependencies, and an automated test enforces this. | Implemented |
| NFR-005 | Auditability | Every result can be traced through the provenance chain: source → raw value → normalised fact → versioned calculation → result. | MVP |
| NFR-010 | Security | Every API endpoint requires authentication unless it explicitly opts out. | Implemented |
| NFR-011 | Security | Secrets come only from the environment. Production refuses to start with a missing or short secret key, empty allowed hosts, or a non-PostgreSQL database. | Implemented |
| NFR-012 | Security | Uploaded documents are stored outside any web-served directory and cannot produce public URLs. | Implemented (storage); MVP (upload API) |
| NFR-013 | Security | Production uses HTTPS, secure cookies, CSRF protection, clickjacking protection and no-sniff headers. | Implemented (settings) |
| NFR-014 | Security | Dependencies are pinned with hashes and audited in CI for known vulnerabilities. | Implemented |
| NFR-015 | Security | API requests are rate-limited: anonymous 60/minute, authenticated 1000/hour (configurable). | Implemented |
| NFR-020 | Privacy | Logs, error responses and audit events never contain financial values, credentials or document contents. | Implemented (logging defaults, error envelope); MVP (audit) |
| NFR-021 | Privacy | No telemetry or third-party calls by default. Optional integrations must be opt-in. | Implemented |
| NFR-022 | Privacy | Users can export and delete their data. | MVP |
| NFR-030 | Accessibility | The web UI meets WCAG 2.1 AA: keyboard navigation, sufficient contrast, labelled forms, and charts with a tabular alternative. | MVP |
| NFR-031 | Accessibility | Numbers are formatted for the user's locale. The currency and scale are always shown next to the figures. | MVP |
| NFR-040 | Reliability | Writes are transactional (one database transaction per request). A failed request leaves no partial data. | Implemented (`ATOMIC_REQUESTS`) |
| NFR-041 | Reliability | The health endpoint returns 503 when the database is unreachable, so orchestrators can react. | Implemented |
| NFR-042 | Reliability | Each request has a request ID, returned in `X-Request-ID` and included in logs. | Implemented |
| NFR-050 | Performance | API reads for one entity and period respond in under 300 ms (p95) on modest self-hosted hardware (2 vCPU, 4 GB RAM) with up to 10,000 statements. | MVP target |
| NFR-051 | Performance | A single-period analysis completes synchronously in under 1 s. Longer work (PDF extraction, bulk import) runs in background jobs. | MVP target; jobs Future |
| NFR-052 | Performance | List endpoints are paginated: 50 items by default, at most 200. | Implemented (default pagination) |
| NFR-060 | Portability | Runs on Windows, macOS and Linux for development, and on any Linux host with PostgreSQL for deployment. No cloud-vendor lock-in. | Implemented (dev); MVP (deployment guide) |
| NFR-061 | Portability | Can be self-hosted without external paid services. | Design constraint |
| NFR-070 | Maintainability | CI runs formatting, linting, strict type checking, Django checks, migration drift checks, tests on PostgreSQL, and a dependency audit on every pull request. | Implemented (CI runs on GitHub; all jobs green, including the PostgreSQL tests) |
| NFR-071 | Maintainability | Material architecture decisions are recorded as ADRs. | Implemented |
| NFR-072 | Maintainability | Module dependency direction is API → application → domain, and infrastructure → domain. The domain imports nothing outward. | Implemented (domain rule) |

## 9. Assumptions

- MVP users are able to enter or prepare statement figures themselves. Finlume does not replace their accounting system.
- A single statement uses one currency and one reporting scale.
- The MVP's canonical taxonomy (21 line items) is enough for the seven MVP ratios. Users can keep extra rows unmapped.
- The MVP is deployed by self-hosters or run locally. A hosted multi-tenant offering, if it ever exists, would need its own review of security, compliance and operations.
- Users understand that results depend on the quality of their inputs. Validation warnings help but cannot prove that inputs are correct.

## 10. Unresolved decisions

| # | Decision | Notes |
|---|----------|-------|
| D-01 | ~~Raise the Python floor from 3.10 to 3.12~~ | **Resolved 2026-10-27:** `requires-python >=3.12`; CI tests 3.12 and 3.13 ([ADR-0002 update](../decisions/ADR-0002-backend-stack.md#update-2026-10-27-python-floor-raised-to-312)). |
| D-02 | Mobile authentication strategy | Token or OIDC-based. To be decided in an ADR when mobile work begins. |
| D-03 | FX conversion policy | Rate source, rate date (period end or average) and how converted figures are labelled. |
| D-04 | Multi-currency reporting | Whether an entity may report in different currencies across periods, and how comparisons are presented. |
| D-05 | Taxonomy extension mechanism | Mapping IFRS, US GAAP and Ind AS line items to Finlume codes, and user-defined line items. |
| D-06 | Average-balance metrics | ROE and ROA on average equity or assets need two consecutive periods. This depends on multi-period support. |
| D-07 | ~~Retention periods~~ | **Resolved 2026-10-27:** the defaults in [Data lifecycle §7](../data/DATA_LIFECYCLE_AND_RETENTION.md#7-retention-periods) are approved. |
| D-08 | Hosted offering | Self-host only, or also an official hosted instance. This affects compliance scope. |
| D-09 | Contact addresses | Email contacts for Code of Conduct and security reports. |
| D-10 | Contribution sign-off | Developer Certificate of Origin (DCO) sign-off, or no sign-off requirement. |

## 11. MVP acceptance criteria

The MVP is accepted when all of the following can be shown on a fresh self-hosted install
using fictional data:

1. A new user registers, signs in and finds their personal workspace (FR-001, FR-003).
2. The user creates a business workspace, invites a second user as viewer, and the viewer can read but not edit (FR-004, FR-005).
3. The user creates a reporting entity and enters a balance sheet, income statement and cash-flow statement for FY2025 in INR crores, by hand (FR-010–FR-012).
4. The user uploads a CSV for another period, reviews the row mapping, confirms it, and sees the normalised figures in base units (FR-013, FR-014).
5. A deliberately unbalanced balance sheet produces a `balance_sheet_imbalance` warning. A negative revenue produces `unexpected_sign`. Neither blocks the analysis (FR-020–FR-023).
6. Running an analysis shows all seven ratios with methodology and inputs. A ratio with a missing input shows "not computable" and a `missing_input` issue, not zero (FR-030–FR-032).
7. The saved analysis shows engine version `0.1.0` (or the current version) and reloads with identical values. Running it again on unchanged inputs gives the same fingerprint and values (FR-033, FR-034, FR-040).
8. Correcting a figure creates statement version 2. The earlier analysis still shows its original inputs and results (FR-017).
9. Every figure on the dashboard can be traced to its source row, its statement version and its source document (NFR-005).
10. Unauthenticated API calls (other than health) return `401` in the standard error envelope. Accessing another workspace's data returns `404` (NFR-010, FR-005, FR-052).
11. A workspace export, followed by a workspace deletion, removes its financial data and private files (FR-054, FR-055).
12. CI is green: lint, types, migration checks, tests on PostgreSQL and the dependency audit (NFR-070).
13. The dashboard passes an automated accessibility check (for example axe) with no critical violations, and is fully usable by keyboard (NFR-030).
