import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { CORRECTION_FIXTURE } from "../../renderer/corrections/corrections-fixture.mjs";
import {
  assertReceiptBackedTerminalStates,
  evidencedDescendants,
  historyFor,
  impactRows,
  requalificationQueue,
  unknownInfluenceRows,
} from "../../renderer/corrections/corrections-model.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, "../../../..");

test("impact closure includes only explicit evidenced descendants", () => {
  const ids = new Set(evidencedDescendants().map((node) => node.id));
  assert.equal(ids.has(CORRECTION_FIXTURE.correction.currentRevision), true);
  for (const excluded of CORRECTION_FIXTURE.nonDescendants) assert.equal(ids.has(excluded), false, excluded);
  for (const edge of CORRECTION_FIXTURE.edges) {
    assert.equal(ids.has(edge.from), true, edge.from);
    assert.equal(ids.has(edge.to), true, edge.to);
  }
});

test("known exposure invalidation requalification and unknown remain distinct states", () => {
  const states = new Set([
    ...impactRows().map((row) => row.state),
    ...CORRECTION_FIXTURE.history.flatMap((entry) => Object.values(entry.states)),
  ]);
  for (const state of ["KNOWN_EXPOSURE", "INVALIDATED", "REQUALIFICATION_REQUIRED", "REQUALIFIED", "UNAVAILABLE_UNKNOWN"]) {
    assert.equal(states.has(state), true, state);
  }
});

test("requalification queue binds exact source revision generation checkpoint and receipts", () => {
  const completed = requalificationQueue().find((task) => task.status === "REQUALIFIED");
  assert.ok(completed);
  assert.equal(completed.sourceRevision, CORRECTION_FIXTURE.correction.currentRevision);
  assert.equal(completed.generation, 44_238);
  assert.match(completed.checkpoint, /^[0-9a-f]{64}$/);
  assert.equal(completed.implicatedRefs.includes("capability:C.SUCCESSOR"), true);
  assert.equal(completed.receiptRefs.length >= 2, true);
});

test("append-only correction history preserves pre-correction state and later receipt", () => {
  const history = historyFor("capability:C.SUCCESSOR");
  assert.deepEqual(history.map((entry) => entry.state), ["REQUALIFICATION_REQUIRED", "REQUALIFIED"]);
  assert.notEqual(history[0].receipt, history[1].receipt);
  assert.equal(history[0].generation < history[1].generation, true);
});

test("untracked downstream neural influence is explicit instead of omitted", () => {
  assert.deepEqual(unknownInfluenceRows().map((row) => row.id), ["neural-influence:untracked:44238"]);
  assert.equal(unknownInfluenceRows()[0].evidenceRefs.length, 0);
});

test("graph and table share one identity-state projection", () => {
  const rows = impactRows();
  const source = fs.readFileSync(path.join(repoRoot, "apps/mission-control/renderer/corrections/corrections-view.mjs"), "utf8");
  assert.match(source, /evidencedDescendants\(\)/);
  assert.match(source, /impactRows\(\)/);
  for (const edge of CORRECTION_FIXTURE.edges) assert.equal(source.includes(edge.relation), false);
  assert.match(source, /CORRECTION_FIXTURE\.edges\.map/);
  assert.equal(new Set(rows.map((row) => `${row.id}:${row.state}`)).size, rows.length);
});

test("requalified and recomputed UI states cannot exist without evidence receipts", () => {
  assert.equal(assertReceiptBackedTerminalStates(), true);
  for (const row of impactRows().filter((item) => ["REQUALIFIED", "RECOMPUTED"].includes(item.state))) {
    assert.equal(row.evidenceRefs.length > 0, true, row.id);
  }
});

test("GUI13 source preserves epistemic limits and contains no mutating correction controls", () => {
  const files = ["corrections-fixture.mjs", "corrections-model.mjs", "corrections-view.mjs"];
  const source = files.map((name) => fs.readFileSync(path.join(repoRoot, "apps/mission-control/renderer/corrections", name), "utf8")).join("\n").toLowerCase();
  assert.equal(source.includes("known exposure is not proof of invalidity"), true);
  assert.equal(source.includes("arbitrary neural influence was erased"), true);
  for (const forbidden of ["apply correction now", "mark requalified", "erase learned influence", "automatic source correction"]) {
    assert.equal(source.includes(forbidden), false, forbidden);
  }
});

test("fixture is grounded in executable correction and CP03 contracts", () => {
  const runtimeEvidence = fs.readFileSync(path.join(repoRoot, "bilqis_mlx/runtime/_correction/atlas_revalidation_evidence.py"), "utf8");
  const runtimeQueue = fs.readFileSync(path.join(repoRoot, "bilqis_mlx/runtime/_correction/atlas_revalidation_queue.py"), "utf8");
  const runtimeRequal = fs.readFileSync(path.join(repoRoot, "bilqis_mlx/runtime/_correction/atlas_requalification_contracts.py"), "utf8");
  const querySupport = fs.readFileSync(path.join(repoRoot, "bilqis_mlx/mission_control/query_support.py"), "utf8");
  assert.match(runtimeEvidence, /class CorrectionEvent/);
  assert.match(runtimeEvidence, /class StateTransition/);
  assert.match(runtimeQueue, /history: tuple\[StateTransition/);
  assert.match(runtimeRequal, /REQUALIFICATION_REQUIRED/);
  assert.match(querySupport, /QueryFamily\.CORRECTION: \(CorrectionEvent,\)/);
});
