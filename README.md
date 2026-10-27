# Finlume

Finlume is an open-source financial intelligence platform designed to make financial analysis more accessible, transparent, and explainable.

Our goal is to help users turn financial data into meaningful insights through reliable calculations, data-driven analysis, and AI-assisted explanations.

## Project Goals

- **Financial Statement Analysis:** Analyze income statements, balance sheets, cash flow statements, and key financial ratios.
- **AI-Powered Insights:** Explain financial trends and findings using evidence from the underlying data.
- **Personal Financial Management:** Help users understand income, expenses, savings, and cash flow.
- **Stock Research:** Explore company fundamentals, financial performance, valuation metrics, and peer comparisons.
- **Portfolio Analytics:** Evaluate allocation, returns, risk, diversification, and rebalancing scenarios.
- **Privacy and Security:** Give users control over their financial data, with local and self-hosted deployment options.
- **Open-Source Collaboration:** Build a transparent, testable financial analysis engine through community contributions.

## Guiding Principle

Financial calculations should be verifiable, AI-generated explanations should be grounded in data, and assumptions and limitations should be clearly communicated.

Finlume is intended to support financial understanding and decision-making, not to guarantee returns or replace qualified professional advice.

## Roadmap

The initial milestone focuses on financial statement ingestion, validated financial calculations, automated tests, and clear analytical reports. Personal finance, stock research, portfolio analytics, and additional AI capabilities will be introduced incrementally.

| Phase | Focus | Status |
|-------|-------|--------|
| 0 | Architecture foundation, backend skeleton, calculation engine core | **In progress** |
| 1 | MVP: manual/CSV financial statements → validation → calculations → saved analysis → web dashboard | Planned |
| 2 | Document and PDF ingestion with human review; background jobs | Planned |
| 3 | AI-assisted explanations grounded in calculated results (optional) | Planned |
| 4 | Personal finance | Planned |
| 5 | Company research with market data; portfolio analytics | Planned |

Mobile apps follow once the web MVP has stabilised the API. Details:
[Product scope](docs/product/PRODUCT_SCOPE.md).

## Current Status

Finlume is at an early stage. **What exists today:**

- a Django + Django REST Framework backend with a versioned API root
  (`/api/v1/`) and a health endpoint;
- the core of the deterministic calculation engine: financial statement
  concepts, consistency checks and seven financial ratios, all covered by
  tests;
- web and mobile client shells that check the backend's health. The web shell
  also has a navigable layout and a sample dashboard built on synthetic data.

Statement entry, saved analyses, real dashboards and everything in later
phases are designed but **not yet implemented**. The clients show empty
states for them rather than invented data.

## Quick Start (backend)

Requires Python 3.12 or 3.13 and Git. On Windows
PowerShell:

Development uses **PostgreSQL**. The documented option runs it with Docker Compose on
port 55432.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # macOS/Linux: source .venv/bin/activate
Copy-Item .env.example .env           # then set POSTGRES_PASSWORD in .env (macOS/Linux: cp)
docker compose up -d db               # PostgreSQL 17 on 127.0.0.1:55432
cd backend
python -m pip install --require-hashes -r requirements/dev.txt
python manage.py dbstatus             # read-only: is the database reachable?
python manage.py migrate
python manage.py runserver
```

Then open <http://127.0.0.1:8000/api/v1/health/>. Without the `POSTGRES_*` settings, Django
stops with a message saying what is missing. SQLite is available only as an explicit opt-in
for throwaway trials. Details, your own PostgreSQL server and running the tests:
[Local setup](docs/development/LOCAL_SETUP.md).

### Backend and web app together

After the one-time setup above, and `npm ci` in `apps/web`, one command from the
repository root starts both. Ctrl+C stops both.

```powershell
.\scripts\dev.ps1     # Windows
./scripts/dev.sh      # Linux
```

This gives the web app at <http://127.0.0.1:5173> and the API at <http://127.0.0.1:8000>.
Details: [Local setup §6](docs/development/LOCAL_SETUP.md#6-start-the-backend-and-web-app-with-one-command).

## Repository Layout

```text
backend/        Django project: config/, apps/ (Django apps), domain/ (pure
                calculation engine), infrastructure/, tests/
apps/web/       React web client (Vite)
apps/mobile/    React Native mobile client (Expo)
docs/           product, architecture, data, API, development docs and ADRs
scripts/        dev launchers (dev.ps1 / dev.sh) and quality-gate runners (check.ps1 / check.sh)
.github/        CI workflow, issue and pull-request templates
compose.yaml    local development PostgreSQL (not a production deployment)
```

## Frontends

| App | Stack | Run |
|---|---|---|
| [`apps/web/`](apps/web/README.md) | React + TypeScript + Vite, Tailwind CSS, TanStack Query, ECharts | `cd apps/web; npm ci; npm run dev` → <http://127.0.0.1:5173> |
| [`apps/mobile/`](apps/mobile/README.md) | React Native + Expo (SDK 58) | `cd apps/mobile; npm ci; npx expo start` |

Both use the same versioned Django API. The web app reaches it through Vite's `/api`
proxy, so start the backend too. Today the only live endpoint they use is the health
check. Every data page shows an honest empty state, and the web dashboard's
**sample** view uses clearly labelled synthetic figures. Details, including which
screens are real and which are sample: [Frontend applications](docs/development/FRONTEND.md).

## Documentation

- [Product scope and requirements](docs/product/PRODUCT_SCOPE.md)
- [System overview](docs/architecture/SYSTEM_OVERVIEW.md) and
  [architecture decisions](docs/architecture/ARCHITECTURE_DECISIONS.md)
- [Data model](docs/data/DATA_MODEL.md) and
  [financial calculation conventions](docs/data/FINANCIAL_CALCULATION_CONVENTIONS.md)
- [Security and privacy](docs/architecture/SECURITY_AND_PRIVACY.md)
- [API conventions](docs/api/API_CONVENTIONS.md)
- [Development workflow](docs/development/DEVELOPMENT_WORKFLOW.md) and
  [quality gates](docs/development/QUALITY_GATES.md)
- [Frontend applications](docs/development/FRONTEND.md)
- [Foundation audit](docs/architecture/FOUNDATION_AUDIT.md) and
  [MVP implementation plan](docs/development/MVP_IMPLEMENTATION_PLAN.md)

## Contributing

Contributions are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) and the
[Code of Conduct](CODE_OF_CONDUCT.md). Report security issues privately as
described in [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE)
