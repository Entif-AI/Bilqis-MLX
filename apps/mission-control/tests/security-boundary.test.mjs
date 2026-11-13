import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const appRoot = path.resolve(here, "..");

test("Electron renderer is isolated from Node and shell access", () => {
  const main = fs.readFileSync(path.join(appRoot, "main.cjs"), "utf8");
  assert.match(main, /contextIsolation:\s*true/);
  assert.match(main, /nodeIntegration:\s*false/);
  assert.match(main, /sandbox:\s*true/);

  for (const file of ["renderer/renderer.mjs", "renderer/shell-state.mjs", "renderer/deep-link.mjs", "preload.cjs"]) {
    const source = fs.readFileSync(path.join(appRoot, file), "utf8");
    assert.doesNotMatch(source, /child_process|spawn\(|exec\(|bilqis_mlx|runs\/|state\.json/);
  }
});
