import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const appRoot = path.resolve(here, "..");
const require = createRequire(import.meta.url);
const {
  createSecureWindowOptions,
  securityDiagnostic,
} = require("../electron/window-security.cjs");
const { RENDERER_ENTRY_URL } = require("../electron/renderer-location.cjs");
const { assertRendererSourceSafe } = require("../electron/renderer-boundary.cjs");

test("GUI01 startup uses the GUI20 window, IPC and custom-protocol boundary", () => {
  const main = fs.readFileSync(path.join(appRoot, "main.cjs"), "utf8");
  assert.match(main, /registerRendererSchemePrivileges\(protocol\)/);
  assert.match(main, /registerMissionControlProtocol\(/);
  assert.match(main, /createMissionControlWindow\(/);
  assert.match(main, /registerMissionControlIpc\(/);
  assert.match(main, /await loadRenderer\(\)/);
  assert.match(main, /AcceptedControlPlaneAdapter/);
  assert.match(main, /createAcceptedValidators/);
  assert.doesNotMatch(main, /loadFile\(/);
  assert.doesNotMatch(main, /bamf:shell-bootstrap/);
  assert.doesNotMatch(main, /createGui01FixtureAdapter|GUI01_FIXTURE_VALIDATORS/);

  const options = createSecureWindowOptions("/fixture/preload.cjs");
  assert.equal(securityDiagnostic(options).passed, true);
  assert.equal(RENDERER_ENTRY_URL, "bamf-mc://app/index.html");
});

test("GUI01 renderer imports no Electron, Node, filesystem or process privilege", () => {
  for (const file of ["renderer.mjs", "shell-state.mjs", "deep-link.mjs", "frames/frame-contract.mjs", "frames/frame-model.mjs", "frames/frame-explorer.mjs", "views/domain-views.mjs"]) {
    const source = fs.readFileSync(path.join(appRoot, "renderer", file), "utf8");
    assert.equal(assertRendererSourceSafe(source, file), true);
  }
});

test("GUI01 renderer is locked to a strict self-only content security policy", () => {
  const source = fs.readFileSync(path.join(appRoot, "renderer", "index.html"), "utf8");
  assert.match(source, /Content-Security-Policy/);
  assert.match(source, /default-src 'self'/);
  assert.match(source, /connect-src 'none'/);
  assert.match(source, /object-src 'none'/);
  assert.match(source, /frame-src 'none'/);
  assert.doesNotMatch(source, /unsafe-eval|unsafe-inline/);
});

test("GUI01 renderer bootstraps through bamfMissionControl, not a raw shell IPC", () => {
  const source = fs.readFileSync(path.join(appRoot, "renderer", "renderer.mjs"), "utf8");
  assert.match(source, /bamfMissionControl\.connect\(\)/);
  assert.match(source, /bamfMissionControl\.querySnapshot\(/);
  assert.doesNotMatch(source, /bamfShell|ipcRenderer|child_process|spawn\(|exec\(/);
});
