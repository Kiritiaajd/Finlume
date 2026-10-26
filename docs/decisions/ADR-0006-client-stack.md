# ADR-0006: Web and mobile client stack

- **Status:** Accepted. **Scaffolded** (2026-10-25): `apps/web/` and `apps/mobile/` exist as shells. See [Implementation notes](#implementation-notes-2026-10-25).
- **Date:** 2026-10-25

## Context

Finlume needs a web application first, for the MVP dashboard and reports, and a mobile application later. Both must consume the same versioned backend API. The foundation phase deliberately does not scaffold either client, so as not to ship empty applications that look production-ready.

## Decision

**Web**, to be built in `apps/web/` when Phase 1 frontend work begins:
- React + TypeScript, built with Vite.
- TanStack Query for server state and API caching.
- React Hook Form + Zod for forms and client-side validation. The server remains the authority.
- Apache ECharts for financial charts.
- Tailwind CSS + shadcn/ui for UI components.

**Mobile**, to be built in `apps/mobile/` after the web MVP stabilises the v1 API:
- React Native + Expo, reusing TypeScript types, Zod schemas and API client code with the web app where practical.

**Shared rules:**
- Both clients use `/api/v1/` exclusively. There are no client-specific backend endpoints unless documented in [API_CONVENTIONS](../api/API_CONVENTIONS.md).
- A typed API client is generated from the backend's OpenAPI schema. Generating that schema with drf-spectacular is planned for Phase 1.
- Clients never calculate financial metrics. They display values computed and stored by the backend engine ([ADR-0003](ADR-0003-deterministic-calculation-engine.md)). Monetary values arrive as strings and are formatted for display, never converted to floats for arithmetic.
- The web app is served from the **same origin** as the API: through a reverse proxy in production, and through the Vite dev-server proxy (`/api` → `http://127.0.0.1:8000`) in development. Session and CSRF authentication then works without CORS, and no CORS dependency is added to the backend.
- Mobile authentication (token-based) gets its own ADR when the mobile phase begins.
- `apps/web/` and `apps/mobile/` are created only when implementation starts, each with its own package manifest and lock file.

## Consequences

### Positive
- One API contract for all clients, with types generated rather than hand-written.
- A mainstream, well-documented stack that is easy for contributors to pick up.
- No CORS surface for the web client.

### Negative
- Root `apps/` (client applications) and `backend/apps/` (Django apps) share a name. Within each subtree the context is unambiguous, and the brief specified `apps/web` and `apps/mobile`, so the naming is accepted.
- Two JavaScript projects to maintain once mobile starts. A shared package (e.g. `packages/api-client`) may be warranted then.

## Alternatives considered

- **`clients/web` and `clients/mobile` instead of `apps/`:** avoids the name overlap, but departs from the agreed repository layout and common monorepo convention. It can be revisited before the first client is created, while renaming is still free.
- **Django templates + HTMX:** simpler, but it does not serve the mobile client and offers weaker rich-charting interactivity.
- **Next.js:** server rendering adds a Node runtime to self-hosted deployments without clear benefit for an authenticated dashboard.
- **Flutter for mobile:** cannot share TypeScript code with the web app.
- **Chart.js / Recharts:** ECharts handles large time series and financial chart types better.

## Implementation notes (2026-10-25)

Both shells were created on the maintainer's request, ahead of the original plan to scaffold
at Phase 1 and post-MVP. To keep the original concern (empty apps looking production-ready)
in check:
- every page without a backend API shows an explicit empty state and disabled actions;
- the only sample data is synthetic, bundled with the web client, and labelled on screen.

See [Frontend applications](../development/FRONTEND.md).

Version choices that differ from "latest":
- **TypeScript 6.0:** typescript-eslint requires TypeScript `<6.1`.
- **React Router 7 and jsdom 29:** their next majors need Node `>=22.22`, and the reference machine runs 22.18.
- **No `@hookform/resolvers`:** 6.0 needs `--legacy-peer-deps`, and 5.9 leads npm 10 to write a lock file that `npm ci` rejects. A small local Zod resolver (`apps/web/src/lib/forms/zod-resolver.ts`, tested) is used instead.
- **Mobile:** versions pinned by Expo SDK 58 (React Native 0.88, React 19.3), plus Expo Router for navigation.

Code sharing between the two clients is deferred until the OpenAPI client exists. Each
currently has its own small, Zod-validated health client.

## Revisit when

- MVP step 6 delivers the OpenAPI schema: generate the typed client and decide on a shared `packages/api-client`.
- The mobile data phase starts: decide mobile authentication (token or OIDC) in its own ADR.
- Node 24 LTS becomes the baseline: move to React Router 8 and jsdom 30.
