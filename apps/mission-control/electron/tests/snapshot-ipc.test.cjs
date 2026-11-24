"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { AcceptedControlPlaneAdapter } = require("../accepted-control-plane-adapter.cjs");
const { createAcceptedValidators, OPERATOR_VIEW_SCHEMA, SNAPSHOT_QUERY_SCHEMA, QUERY_PAGE_SCHEMA } =
  require("../accepted-contracts.cjs");
const { ControlPlaneBridge } = require("../control-plane-bridge.cjs");
const { registerMissionControlIpc } = require("../main-ipc.cjs");
const { CHANNELS } = require("../channels.cjs");
const { RENDERER_ENTRY_URL, RENDERER_ORIGIN } = require("../shell/renderer-location.cjs");
const operatorView = require("../../fixtures/operator-view-v1.json");

test("live snapshot gaps and stale records cross IPC as availability, while invalid pages fail closed", async () => {
  const { assertOperatorView } = await import("../../renderer/shell-state.mjs");
  const handlers = new Map();
  const ipcMain = { handle: (key, fn) => handlers.set(key, fn), removeHandler: (key) => handlers.delete(key) };
  const frame = { url: RENDERER_ENTRY_URL, origin: RENDERER_ORIGIN };
  frame.top = frame;
  const sender = { id: 17, mainFrame: frame };
  const event = { sender, senderFrame: frame };
  const failures = [];
  let state = "PRESENT";
  let records = [operatorView];
  let malformed = false;
  const broker = {
    async connect() {
      return {
        schemaVersion: "bamf.gui20.cp01-status/v1", state: "healthy",
        protocolVersion: "bilqis.bamf.control-plane/v1", serviceLive: true,
        serviceReady: true, learnerReady: true, learnerActive: true,
        learnerState: "healthy", runId: "fixture-run", generation: 7,
        optimizerStep: 19, failureCode: null,
      };
    },
    async query(request) {
      return {
        schema: QUERY_PAGE_SCHEMA, query_id: "a".repeat(64), request,
        family: request.family, mode: request.mode, state,
        coverage: state === "PRESENT" ? "COMPLETE" : "UNKNOWN",
        total_matches: records.length, returned: malformed ? 2 : records.length,
        truncated: false, next_cursor: null, records, markers: [], links: [], accepted: true,
      };
    },
  };
  const bridge = new ControlPlaneBridge(
    new AcceptedControlPlaneAdapter({ broker }), createAcceptedValidators(assertOperatorView));
  registerMissionControlIpc({
    ipcMain, bridge, trustedWebContents: sender, onRequestFailure: (failure) => failures.push(failure),
  });
  await handlers.get(CHANNELS.connect)(event);
  const snapshot = () => handlers.get(CHANNELS.snapshot)(event, {
    schemaVersion: SNAPSHOT_QUERY_SCHEMA, schema: OPERATOR_VIEW_SCHEMA,
  });
  assert.deepEqual(await snapshot(), operatorView);
  state = "UNAVAILABLE";
  records = [];
  assert.deepEqual(await snapshot(), {
    schemaVersion: "bamf.gui20.operator-view-unavailable/v1", state: "UNAVAILABLE",
  });
  state = "STALE";
  records = [operatorView];
  assert.deepEqual(await snapshot(), {
    schemaVersion: "bamf.gui20.operator-view-unavailable/v1", state: "STALE",
  });
  assert.deepEqual(failures, []);
  state = "UNAVAILABLE";
  records = [];
  malformed = true;
  await assert.rejects(snapshot(), /BAMF_GUI20_CONTROL_PLANE_REQUEST_FAILED/);
  assert.equal(failures.length, 1);
  malformed = false;
  state = "PRESENT";
  records = [operatorView];
  assert.deepEqual(await snapshot(), operatorView);
});
