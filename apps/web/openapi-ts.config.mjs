// TypeScript types for the v1 API, generated from the committed OpenAPI contract
// (docs/api/openapi-v1.yaml). Types only: no runtime client code.
//
//   npm run api:types         regenerate src/api/generated/
//   npm run api:types:check   fail if src/api/generated/ is out of date
import { defineConfig } from "@hey-api/openapi-ts";

/** Shared with scripts/check-api-types.mjs, which regenerates into a temporary folder. */
export const settings = {
  input: "../../docs/api/openapi-v1.yaml",
  output: "src/api/generated",
  plugins: ["@hey-api/typescript"],
  logs: { file: false },
};

export default defineConfig(settings);
