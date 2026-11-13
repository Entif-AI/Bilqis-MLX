import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { renderComponentCatalog } from "../renderer/component-catalog.mjs";
import { DENSITIES, THEMES, loadDisplaySettings, saveDisplaySettings } from "../renderer/settings.mjs";
import { semanticStateInventory, statusBadge, evidenceValue } from "../renderer/visual-language.mjs";
import { VISUAL_REGRESSION_CASES, visualFixtureNames } from "../renderer/visual-fixtures.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const rendererRoot = path.resolve(here, "../renderer");

function fakeStorage(initial = {}) {
  const values = new Map(Object.entries(initial));
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    snapshot: () => Object.fromEntries(values),
  };
}

test("semantic inventory covers every GUI02 state with non-color markers", () => {
  const expected = [
    "healthy", "attention", "invalid",
    "held", "unavailable", "denied", "unknown", "stale", "partial",
    "proposed", "accepted", "attempted", "reconciled",
    "live", "historical",
  ];
  assert.deepEqual(semanticStateInventory(), expected);
  for (const state of expected) {
    const html = statusBadge(state);
    assert.match(html, new RegExp('data-state="' + state + '"'));
    assert.match(html, /<span aria-hidden="true">.+<\/span>/);
  }
});

test("measured/inferred and source/derived carry independent textual and structural cues", () => {
  const measuredSource = evidenceValue("91%", "measured", "source");
  const inferredDerived = evidenceValue("≈ 91%", "inferred", "derived");
  assert.match(measuredSource, /data-evidence="measured"/);
  assert.match(measuredSource, /data-authority="source"/);
  assert.match(measuredSource, /Measured/);
  assert.match(measuredSource, /Source-authoritative/);
  assert.match(inferredDerived, /data-evidence="inferred"/);
  assert.match(inferredDerived, /data-authority="derived"/);
  assert.match(inferredDerived, /Estimated \/ inferred/);
  assert.match(inferredDerived, /Learned \/ derived/);
});

test("component catalog includes every required common treatment", () => {
  const html = renderComponentCatalog();
  for (const marker of [
    "metric-tile", "status-badge", "provenance-chip", "run-identity", "trend",
    "comparison-card", "alert", "state-surface", "evidence-row", "graph-legend",
    "historical-banner",
  ]) assert.match(html, new RegExp(marker));
});

test("theme and density settings persist only in UI-local keys", () => {
  const storage = fakeStorage();
  saveDisplaySettings(storage, { theme: "light", density: "terminal" });
  assert.deepEqual(loadDisplaySettings(storage), { theme: "light", density: "terminal" });
  assert.deepEqual(Object.keys(storage.snapshot()).sort(), ["bilqis.mc.density", "bilqis.mc.theme"]);
  assert.deepEqual(THEMES, ["dark", "light"]);
  assert.deepEqual(DENSITIES, ["comfortable", "compact", "terminal"]);
});

test("visual regression fixtures cover required safety postures", () => {
  assert.deepEqual(visualFixtureNames(), ["live", "historical", "stale", "denied", "invalidEvidence"]);
  assert.equal(VISUAL_REGRESSION_CASES.length, 10);
  assert.deepEqual(
    new Set(VISUAL_REGRESSION_CASES.map(({ theme }) => theme)),
    new Set(["dark", "light"]),
  );
  for (const fixture of visualFixtureNames()) {
    assert.equal(VISUAL_REGRESSION_CASES.filter((entry) => entry.fixture === fixture).length, 2);
  }
});

test("CSS supplies non-color cues and terminal density without horizontal table forcing", () => {
  const css = ["visual-tokens.css", "components.css", "shell.css"]
    .map((name) => fs.readFileSync(path.join(rendererRoot, name), "utf8"))
    .join("\n");
  assert.match(css, /border-style:\s*dashed/);
  assert.match(css, /border-style:\s*double/);
  assert.match(css, /border-style:\s*dotted/);
  assert.match(css, /repeating-linear-gradient/);
  assert.match(css, /data-density="terminal"/);
  assert.doesNotMatch(css, /\.catalog[^\{]*\{[^}]*overflow-x:\s*scroll/);
});

test("dark and light themes expose the same semantic token surface", () => {
  const css = fs.readFileSync(path.join(rendererRoot, "visual-tokens.css"), "utf8");
  for (const token of ["--canvas", "--surface-1", "--border", "--text", "--text-muted", "--healthy", "--attention", "--invalid", "--historical"]) {
    assert.equal(css.split(token).length - 1 >= 2, true, token + " missing from one theme");
  }
});
