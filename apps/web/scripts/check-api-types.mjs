// Fails when src/api/generated/ no longer matches docs/api/openapi-v1.yaml.
//
// It regenerates the types into a temporary folder with the committed
// configuration and compares every file. The backend separately checks that
// the committed YAML matches the live API (tests/api/test_schema.py).
import { mkdtemp, readdir, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { createClient } from "@hey-api/openapi-ts";

import { settings } from "../openapi-ts.config.mjs";

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const committed = path.join(root, settings.output);
const fresh = await mkdtemp(path.join(tmpdir(), "finlume-api-types-"));

async function files(dir) {
  const entries = await readdir(dir, { recursive: true, withFileTypes: true });
  return entries
    .filter((entry) => entry.isFile())
    .map((entry) => path.relative(dir, path.join(entry.parentPath, entry.name)))
    .sort();
}

const read = async (file) => (await readFile(file, "utf8")).replaceAll("\r\n", "\n");

try {
  process.chdir(root);
  await createClient({ ...settings, output: fresh, logs: { file: false, level: "silent" } });

  const expected = await files(fresh);
  const actual = await files(committed).catch(() => []);
  const problems = [];
  for (const name of new Set([...expected, ...actual])) {
    if (!expected.includes(name)) problems.push(`unexpected file ${name}`);
    else if (!actual.includes(name)) problems.push(`missing file ${name}`);
    else if ((await read(path.join(fresh, name))) !== (await read(path.join(committed, name))))
      problems.push(`${name} differs`);
  }
  if (problems.length) {
    console.error(
      `src/api/generated/ is out of date with docs/api/openapi-v1.yaml:\n  ${problems.join("\n  ")}\n` +
        "Run: npm run api:types",
    );
    process.exitCode = 1;
  } else {
    console.log("API types match docs/api/openapi-v1.yaml.");
  }
} finally {
  await rm(fresh, { recursive: true, force: true });
}
