/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Browser-visible API origin; empty means same origin (see .env.example). */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

/** Injected by vite.config.ts from package.json. */
declare const __APP_VERSION__: string;
