import test from "node:test";
import assert from "node:assert/strict";
import {
  DESTINATIONS,
  createShellState,
  inspect,
  navigate,
  openSelectionOwner,
  shellPosture,
} from "../renderer/shell-state.mjs";
import { buildDeepLink, parseDeepLink } from "../renderer/deep-link.mjs";

const context = {
  runId: "run-1",
  mode: "LIVE",
  generation: 42,
  checkpoint: "cp-42",
  topologyId: "topology-1",
  freshness: "FRESH",
};

test("all required GUI01 destinations remain stable and reachable", () => {
  assert.deepEqual(
    DESTINATIONS.map(([id]) => id),
    ["mission-control", "school", "learning", "atlas", "model", "memory", "teacher", "corrections", "lineage", "resources", "evidence", "operate"],
  );
});

test("switching views preserves exact inspected context", () => {
  const initial = createShellState(context);
  const next = navigate(initial, "atlas");
  assert.equal(next.view, "atlas");
  assert.equal(next.context, initial.context);
  assert.equal(next.context.generation, 42);
  assert.equal(next.context.runId, "run-1");
});

test("deep links restore view and selected object without encoding run context", () => {
  const initial = inspect(navigate(createShellState(context), "evidence"), {
    kind: "evidence",
    id: "receipt:123",
  });
  const hash = buildDeepLink(initial);
  assert.equal(hash, "#/view/evidence?kind=evidence&id=receipt%3A123");
  const restored = createShellState(context, parseDeepLink(hash));
  assert.equal(restored.context.runId, "run-1");
  assert.deepEqual(restored.selected, { kind: "evidence", id: "receipt:123" });
});

test("historical and stale states are shell-global postures", () => {
  assert.equal(shellPosture(createShellState({ ...context, mode: "HISTORICAL" }).context), "historical");
  assert.equal(shellPosture(createShellState({ ...context, freshness: "STALE" }).context), "stale");
  assert.equal(shellPosture(createShellState(context).context), "live");
});

test("inspector routes at least five stable object classes to owning views", () => {
  const samples = [
    ["capability", "school"],
    ["episode", "learning"],
    ["semantic", "atlas"],
    ["memory", "memory"],
    ["checkpoint", "lineage"],
    ["evidence", "evidence"],
    ["correction", "corrections"],
    ["warning", "resources"],
  ];
  for (const [kind, owner] of samples) {
    const selected = inspect(createShellState(context), { kind, id: `${kind}:1` });
    const opened = openSelectionOwner(selected);
    assert.equal(opened.view, owner);
    assert.equal(opened.context, selected.context);
  }
});
