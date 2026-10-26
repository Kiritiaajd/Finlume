/**
 * Runtime configuration, read once from Vite's environment.
 *
 * `VITE_API_BASE_URL` is empty by default: the browser calls `/api/v1/...` on
 * its own origin, and Vite's dev proxy (or the production reverse proxy)
 * forwards to Django. See `.env.example`.
 */
const configuredBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? "").trim();

export const config = {
  apiBaseUrl: configuredBaseUrl.replace(/\/+$/, ""),
  apiVersionPath: "/api/v1",
  appVersion: __APP_VERSION__,
} as const;

/** Absolute or origin-relative URL for a path under the versioned API. */
export function apiUrl(path: string): string {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${config.apiBaseUrl}${config.apiVersionPath}${normalized}`;
}
