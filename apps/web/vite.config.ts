/// <reference types="vitest/config" />
import { readFileSync } from "node:fs";
import { fileURLToPath, URL } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

const pkg = JSON.parse(readFileSync(new URL("./package.json", import.meta.url), "utf-8")) as {
  version: string;
};

export default defineConfig(({ mode }) => {
  // Loaded without a prefix filter so the server-only proxy target can be read
  // here without being exposed to client code (only VITE_* reaches the browser).
  const env = loadEnv(mode, process.cwd(), "");
  const apiProxyTarget = env.FINLUME_API_PROXY_TARGET || "http://127.0.0.1:8000";

  // Same-origin development: the browser only ever talks to Vite, which
  // forwards /api to Django. The Host header is left as-is (no changeOrigin)
  // so Django's CSRF origin check behaves exactly as behind the production
  // reverse proxy, and no CORS configuration is needed.
  const proxy = { "/api": { target: apiProxyTarget, changeOrigin: false } };

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
    },
    define: {
      __APP_VERSION__: JSON.stringify(pkg.version),
    },
    server: { host: "127.0.0.1", port: 5173, strictPort: true, proxy },
    preview: { host: "127.0.0.1", port: 4173, strictPort: true, proxy },
    build: {
      sourcemap: true,
      // Two known chunks sit near 550 kB minified (~180 kB gzip): the app core
      // (React, router, query, zod) and ECharts, which is lazy-loaded with the
      // sample dashboard. Warn on anything larger.
      chunkSizeWarningLimit: 600,
    },
    test: {
      environment: "jsdom",
      setupFiles: ["./src/test/setup.ts"],
      css: false,
      restoreMocks: true,
    },
  };
});
