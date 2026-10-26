# Frontend applications

Finlume has two client applications under the repository root's `apps/`, beside (not
inside) the Django project in `backend/`. Each has its own `package.json` and lock file.
They share no dependencies with each other or with the Python backend.

| Path | Stack | Status |
|---|---|---|
| [`apps/web/`](../../apps/web/README.md) | React 19, TypeScript 6, Vite 8, Tailwind CSS 4 (shadcn/ui conventions), TanStack Query 5, React Router 7, React Hook Form + Zod 4, Apache ECharts 6 | Application shell with five pages, a live API health check and a synthetic sample dashboard |
| [`apps/mobile/`](../../apps/mobile/README.md) | Expo SDK 58, React Native 0.88, React 19.3, Expo Router, Zod 4 | Welcome/dashboard shell with a live API health check |

Root `apps/` holds client applications; `backend/apps/` holds Django apps. The overlap in
names is accepted in [ADR-0006](../decisions/ADR-0006-client-stack.md).

## Running everything locally

**Backend and web together:** `.\scripts\dev.ps1` (Windows) or `./scripts/dev.sh` (Linux)
from the repository root. Ctrl+C stops both. See
[Local setup §6](LOCAL_SETUP.md#6-start-the-backend-and-web-app-with-one-command) for
prerequisites, options and troubleshooting. The mobile app is not started by the launcher.

**Or by hand,** in three terminals, starting from the repository root with the Python
virtual environment active for the first one. The backend needs its PostgreSQL database
configured in `.env` and running; see
[Local setup §3](LOCAL_SETUP.md#3-database-postgresql-the-development-default).

```powershell
# 1. Backend: http://127.0.0.1:8000 (database already running, e.g. docker compose up -d db)
cd backend
python manage.py dbstatus      # read-only check; then migrate if it reports pending migrations
python manage.py runserver

# 2. Web: http://127.0.0.1:5173
cd apps/web
npm ci
npm run dev

# 3. Mobile: Expo dev server; open in Expo Go or an emulator
cd apps/mobile
npm ci
npx expo start
```

For the mobile app to reach Django from a device, follow the
[mobile connection steps](../../apps/mobile/README.md#connecting-to-the-django-api-development).

## How the clients talk to Django

```text
Browser ──► Vite dev server :5173 ──/api/*──► Django :8000   (development)
Browser ──► reverse proxy (TLS) ──/api/*──► Django/Gunicorn   (production, planned)
Phone   ──► EXPO_PUBLIC_API_BASE_URL/api/v1/…  ──────────────► Django   (development)
```

- **Web, same origin.** The browser calls `/api/v1/...` on the web app's own origin. In development, Vite's proxy (`vite.config.ts`) forwards `/api` to `FINLUME_API_PROXY_TARGET` (default `http://127.0.0.1:8000`). It keeps the original `Host` header (`changeOrigin: false`), so Django's CSRF origin check works as it will behind the production reverse proxy. There is no CORS: the backend has no CORS middleware, and none is needed.
- **Typed client.** `apps/web/src/lib/api/client.ts` validates every response with Zod and classifies failures:
  - `ApiUnavailableError`: the API cannot be reached, for example the network failed or Vite's proxy answered `502` because Django is not running;
  - `ApiResponseError`: the backend's documented error envelope;
  - `ApiContractError`: the API answered in an unexpected shape.
- **Health check.** `GET /api/v1/health/` is polled every 30 s through TanStack Query. `200` means connected. A `503` that still has the health body means the API is running but its database is not (degraded).
- **Mobile.** Calls the same endpoint at `EXPO_PUBLIC_API_BASE_URL`, with the same states.
- **Decimals.** The API sends decimals as strings. The clients format them with `Intl.NumberFormat` directly from the string, never via binary floats, and never calculate financial metrics ([ADR-0003](../decisions/ADR-0003-deterministic-calculation-engine.md)). Chart libraries need numbers to draw, so charts convert for plotting only. Exact values appear in the accompanying data tables.

## What is real and what is sample

| Screen | Data source |
|---|---|
| Web: API status (sidebar, dashboard, settings) | **Real**: `GET /api/v1/health/` |
| Web: Dashboard → "Your data" | **Real empty state.** No data API exists yet; the "Add a statement" action is disabled with the reason given |
| Web: Dashboard → "Sample dashboard" | **Synthetic.** Invented figures for "Sample Company (fictional)", bundled in `src/features/sample/sampleData.ts`. Labelled on screen; not from the backend or the engine |
| Web: Financial statements, Analysis, Reports | **Empty states** with disabled actions. The metric catalogue on Analysis is a static description of the engine's formulas, with no figures |
| Web: Settings → Display preferences | **Local only.** Stored in this browser's `localStorage`; there are no accounts yet |
| Mobile: Dashboard and Connection | **Real** health check, and an empty state. No sample data |

There is no sign-in, and neither client simulates one.

## Quality checks

| App | Command | Covers |
|---|---|---|
| Web | `npm run check` | `tsc -b`, ESLint, Vitest (API client states, decimal formatting, sample-data consistency, routing, empty, error and unavailable states, settings form), production build |
| Mobile | `npm run typecheck`, `npm run doctor`, `npm run bundle:check` | TypeScript, Expo dependency checks, Metro bundling for Android |

CI runs the web check and the mobile typecheck and doctor in `.github/workflows/ci.yml`.

## Version notes

- **TypeScript 6.0, not 7.** typescript-eslint supports TypeScript `<6.1`.
- **React Router 7, not 8.** React Router 8 requires Node `>=22.22`. Likewise jsdom 29 rather than 30. Upgrading Node to 24 LTS would allow both.
- **No `@hookform/resolvers`.** Version 6 cannot be installed without `--legacy-peer-deps`. With 5.9, npm 10 writes a lock file that `npm ci` then rejects (its optional `ajv@8` peer clashes with ESLint's `ajv@6`). A tested 30-line resolver in `src/lib/forms/zod-resolver.ts` connects React Hook Form to Zod instead. Revisit if the upstream peer list is trimmed.
- **Mobile versions are pinned by the Expo SDK.** Add native packages with `npx expo install <package>`, never with a plain `npm install`.

## Current limitations

- No authentication, workspaces or data screens. They follow the backend APIs in the [MVP plan](MVP_IMPLEMENTATION_PLAN.md) (steps 1–5, then step 7 for the full dashboard).
- No generated API types yet: the OpenAPI schema is MVP step 6. The health client is hand-written and validated with Zod.
- No end-to-end (Playwright) or automated accessibility (axe) tests yet. Both are planned with step 7.
- The mobile app has no component tests and inherits upstream `npm audit` advisories in Expo's CLI tooling (see its README).
- The production build is not yet served by any deployment configuration (MVP step 8).
