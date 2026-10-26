/**
 * Base URL of the Finlume Django server, for example `http://192.168.1.20:8000`.
 *
 * Expo inlines `EXPO_PUBLIC_*` variables at build time (see `.env.example`).
 * A phone cannot reach the developer machine's `127.0.0.1`, so there is no
 * default: until it is set, the app reports the API as "not configured".
 * Never put secrets in `EXPO_PUBLIC_*` variables; they ship inside the app.
 */
const configured = process.env.EXPO_PUBLIC_API_BASE_URL?.trim() ?? "";

export const API_BASE_URL = configured.replace(/\/+$/, "");
export const API_VERSION_PATH = "/api/v1";
export const isApiConfigured = API_BASE_URL.length > 0;
