import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import { createBootstrapController } from "../renderer/foundation/bootstrap-controller.mjs";

const OPERATOR_VIEW = JSON.parse(readFileSync(
  new URL("../fixtures/operator-view-v1.json", import.meta.url), "utf8",
));

function storageFixture() {
  return {
    getItem() { return null; },
    setItem() {},
    removeItem() {},
  };
}

test("disconnected bootstrap schedules automatic reconnect without operator clicks", async () => {
  let connectCalls = 0;
  const scheduled = [];
  const api = {
    async connect() {
      connectCalls += 1;
      return {
        state: "disconnected",
        serviceLive: false,
        serviceReady: false,
        learnerReady: false,
      };
    },
    async querySnapshot() {
      throw new Error("CONTROL_PLANE_NOT_CONNECTED");
    },
  };
  const controller = createBootstrapController({
    api,
    storage: storageFixture(),
    getState: () => null,
    setState() {},
    setDefense() {},
    setBootstrap() {},
    setVerifiedLiveContext() {},
    resetFrameShell() {},
    render() {},
    announce() {},
    currentHash: () => "",
    scheduleReconnect: (callback, _delay) => {
      scheduled.push(callback);
      return scheduled.length;
    },
    cancelReconnect() {},
    reconnectDelayMs: 25,
  });

  await controller.establishSnapshot();
  assert.equal(connectCalls, 1);
  assert.equal(scheduled.length, 1);

  await scheduled.shift()();
  assert.equal(connectCalls, 2);
});

test("transient live operator-view gaps preserve the last good shell state", async () => {
  const scheduled = [];
  const defenses = [];
  let connectCalls = 0;
  let statusCalls = 0;
  let snapshotCalls = 0;
  let resetCalls = 0;
  let state = {
    view: "capability",
    context: { runId: "fixture-run", generation: 7, mode: "LIVE", freshness: "FRESH" },
    selected: { kind: "capability", id: "B.AND" },
    mutationAvailable: true,
  };
  let verifiedLiveContext = state.context;
  const api = {
    async connect() {
      connectCalls += 1;
      return {
        state: "healthy",
        serviceLive: true,
        serviceReady: true,
        learnerReady: true,
      };
    },
    async status() {
      statusCalls += 1;
      return {
        state: "healthy",
        serviceLive: true,
        serviceReady: true,
        learnerReady: true,
      };
    },
    async querySnapshot() {
      snapshotCalls += 1;
      return snapshotCalls === 1 ? {
        schemaVersion: "bamf.gui20.operator-view-unavailable/v1",
        state: "UNAVAILABLE",
      } : structuredClone(OPERATOR_VIEW);
    },
  };
  const controller = createBootstrapController({
    api,
    storage: storageFixture(),
    getState: () => state,
    setState: (next) => { state = next; },
    setDefense: (next) => { defenses.push(next); },
    setBootstrap() {},
    setVerifiedLiveContext: (next) => { verifiedLiveContext = next; },
    resetFrameShell() { resetCalls += 1; },
    render() {},
    announce() {},
    currentHash: () => "",
    scheduleReconnect: (callback, _delay) => {
      scheduled.push(callback);
      return scheduled.length;
    },
    cancelReconnect() {},
    reconnectDelayMs: 25,
  });

  await controller.establishSnapshot();

  assert.notEqual(state, null);
  assert.equal(state.view, "capability");
  assert.deepEqual(state.selected, { kind: "capability", id: "B.AND" });
  assert.equal(state.mutationAvailable, false);
  assert.equal(defenses.at(-1).snapshotAvailable, true);
  assert.equal(defenses.at(-1).snapshotSource, "previous");
  assert.equal(verifiedLiveContext, null);
  assert.equal(scheduled.length, 1);

  await scheduled.shift()();
  assert.equal(connectCalls, 1);
  assert.equal(statusCalls, 1);
  assert.equal(snapshotCalls, 2);
  assert.notEqual(state, null);
  assert.equal(state.view, "capability");
  assert.equal(state.context.runId, "fixture-run");
  assert.equal(state.context.generation, 7);
  assert.equal(defenses.at(-1).id, "live");
  assert.equal(verifiedLiveContext.runId, "fixture-run");
  assert.equal(resetCalls, 2);
});
