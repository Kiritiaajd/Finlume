# Finlume web client

React + TypeScript single-page app for Finlume, built with Vite. It talks to
the Django backend only through the versioned API (`/api/v1/`).

**Status:** foundation. The only backend endpoint in use is the public health
check. Every other page shows an empty state with disabled actions until the
matching API exists. The dashboard offers an optional, clearly labelled
**synthetic** sample. See [what is real and what is sample](../../docs/development/FRONTEND.md#what-is-real-and-what-is-sample).

## Requirements

- Node.js `^22.13` or `>=24` (developed on 22.18) and npm 10+.
- The Finlume backend running locally, for live API status. The UI still works without it and reports the API as unavailable.

## Run

```powershell
cd apps/web
npm ci                # exact versions from package-lock.json
npm run dev           # http://127.0.0.1:5173
```

In another terminal, start Django (see the [repository README](../../README.md#quick-start-backend)):

```powershell
cd backend
python manage.py runserver   # http://127.0.0.1:8000
```

Or start both from the repository root with `.\scripts\dev.ps1` (Windows) or
`./scripts/dev.sh` (Linux); see [Local setup §6](../../docs/development/LOCAL_SETUP.md#6-start-the-backend-and-web-app-with-one-command).

Vite forwards every `/api` request to Django, so the browser only ever talks to one
origin.

## Scripts

| Command | What it does |
|---|---|
| `npm run dev` | Development server with hot reload and the `/api` proxy |
| `npm run typecheck` | TypeScript project build (`tsc -b`, no output) |
| `npm run lint` | ESLint (TypeScript, React Hooks, React Refresh rules) |
| `npm test` | Vitest + Testing Library in jsdom |
| `npm run build` | Typecheck, then a production build into `dist/` |
| `npm run preview` | Serve `dist/` locally, with the same `/api` proxy |
| `npm run check` | All of the above except `dev`/`preview` |

## Configuration

Copy `.env.example` to `.env.local` (git-ignored) only if you need to change a default.

| Variable | Used by | Default | Meaning |
|---|---|---|---|
| `VITE_API_BASE_URL` | Browser bundle | empty | API origin. Empty means same origin, which is the supported setup. |
| `FINLUME_API_PROXY_TARGET` | Dev and preview servers only | `http://127.0.0.1:8000` | Where Vite forwards `/api`. Never sent to the browser. |

No secrets belong in these files: every `VITE_*` value is visible in the
built JavaScript.

## Structure

```text
src/
  main.tsx, routes.tsx, AppProviders.tsx   entry point, routes, providers
  index.css                                Tailwind v4 + design tokens (light/dark)
  components/ui/                           shadcn/ui-style primitives (see components.json)
  components/                              app shell, API status, empty states, charts
  features/sample/                         SYNTHETIC sample dashboard (lazy-loaded)
  lib/api/                                 typed API client, error classes, health check
  lib/                                     config, formatting, preferences, utilities
  pages/                                   one component per route
  test/                                    test setup and helpers
```

Conventions:
- Data fetching goes through TanStack Query.
- Responses are validated with Zod before use.
- Monetary values stay decimal strings and are formatted with `Intl.NumberFormat` without converting to floats.
- The client never calculates financial metrics ([ADR-0003](../../docs/decisions/ADR-0003-deterministic-calculation-engine.md)).
