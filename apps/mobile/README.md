# Finlume mobile client

React Native app built with Expo (SDK 58, React Native 0.88, React 19.3) and
Expo Router. It is a **shell**:
- a welcome dashboard with an empty state;
- a connection screen;
- a live check of the backend's public health endpoint.

It shows no sample or invented financial data.

## Requirements

- Node.js 22 LTS and npm.
- To run the app, either:
  - [Expo Go](https://expo.dev/go) on a phone on the same network, or
  - an Android emulator (Android Studio) or iOS simulator (macOS only).

## Run

```powershell
cd apps/mobile
npm ci
npx expo start        # scan the QR code with Expo Go, or press a / i for an emulator
```

Without configuration the app runs and reports the API as **Not configured**.

## Connecting to the Django API (development)

A phone cannot reach `127.0.0.1` on your computer, so the API address is explicit:

1. Start Django on your network interface: `python manage.py runserver 0.0.0.0:8000` (in `backend/`).
2. Add your computer's LAN IP to `DJANGO_ALLOWED_HOSTS` in the repository's `.env`, for example `localhost,127.0.0.1,192.168.1.20`.
3. Copy `.env.example` to `.env` here and set `EXPO_PUBLIC_API_BASE_URL=http://192.168.1.20:8000`.
4. Restart with `npx expo start --clear` so the value is bundled.

The app then calls `GET /api/v1/health/`, the same versioned API the web client uses.
Use this only with a development server on a network you trust, because the traffic is
plain HTTP. `EXPO_PUBLIC_*` values are compiled into the app, so never put secrets in them.

## Plan for the full API connection

Follows [ADR-0006](../../docs/decisions/ADR-0006-client-stack.md); not implemented yet.

1. **Authentication first.** The web client uses session cookies with CSRF, which suits browsers but not native apps. A future ADR will choose token- or OIDC-based authentication. Tokens would be stored with `expo-secure-store`, never in AsyncStorage.
2. **Shared, generated types.** Once the backend publishes its OpenAPI schema (MVP step 6), generate a TypeScript client. Possibly share it with the web app as a `packages/api-client` workspace, together with the Zod response schemas.
3. **Same conventions as the web client.** Data fetching through TanStack Query; decimal strings formatted for display only; the backend's error envelope (`code`, `message`, `request_id`) shown to the user.
4. **HTTPS-only builds.** Release builds would only talk to an HTTPS API. The plain-HTTP development setup above would be limited to development builds.

## Checks

| Command | What it does |
|---|---|
| `npm run typecheck` | `tsc --noEmit` |
| `npm run doctor` | `expo-doctor`: dependency and configuration checks (needs network) |
| `npm run bundle:check` | Bundles the JavaScript for Android with Metro into `dist/` (no Android SDK needed) |

## Known limitations

- No authentication, data screens or offline storage yet.
- No automated component tests yet; Jest with `jest-expo` is planned with the first data screens.
- **`npm audit` reports advisories inside Expo's own CLI tooling** (`@expo/cli` → `node-forge` ≤ 1.4.0 and a bundled `zod` 3.25.x). They come from the development toolchain, not the app's JavaScript bundle. As of 2026-10-25 no patched release exists on those lines. Do not run `npm audit fix --force`: it "fixes" them by downgrading Expo to SDK 44. Re-check when Expo publishes an update.

## Licence note

Finlume is MIT-licensed (see the repository [LICENSE](../../LICENSE)). This project was
generated from Expo's `blank-typescript` template. The template's own MIT notice
(© 650 Industries, Inc.) is kept in [`EXPO_TEMPLATE_LICENSE`](EXPO_TEMPLATE_LICENSE) for
the template-derived configuration files and assets.
