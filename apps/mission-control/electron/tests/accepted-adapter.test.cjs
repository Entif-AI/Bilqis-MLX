"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const {
  AcceptedControlPlaneAdapter,
  disconnectedStatus,
} = require("../accepted-control-plane-adapter.cjs");
const {
  OPERATOR_VIEW_SCHEMA,
  SNAPSHOT_QUERY_SCHEMA,
  createAcceptedValidators,
} = require("../accepted-contracts.cjs");
const { ControlPlaneBridge } = require("../control-plane-bridge.cjs");

function brokerFixture({ fail = false } = {}) {
  const calls = [];
  return {
    calls,
    async connect() {
      calls.push("connect");
      if (fail) throw new Error("socket path must not escape");
      return {
        schemaVersion: "bamf.gui20.cp01-status/v1",
        state: "learner-unavailable",
        protocolVersion: "bilqis.bamf.control-plane/v1",
        serviceLive: true,
        serviceReady: true,
        learnerReady: false,
        learnerActive: false,
      };
    },
    async status() {
      calls.push("status");
      if (fail) throw new Error("private run path");
      return {
        schemaVersion: "bamf.gui20.cp01-status/v1",
        state: "healthy",
        protocolVersion: "bilqis.bamf.control-plane/v1",
        serviceLive: true,
        serviceReady: true,
        learnerReady: true,
        learnerActive: true,
      };
    },
    async disconnect() { calls.push("disconnect"); },
    close() { calls.push("close"); },
  };
}

async function acceptedBridge(broker) {
  const { assertOperatorView } = await import("../../renderer/shell-state.mjs");
  const adapter = new AcceptedControlPlaneAdapter({ broker });
  return {
    adapter,
    bridge: new ControlPlaneBridge(adapter, createAcceptedValidators(assertOperatorView)),
  };
}

test("accepted adapter uses CP01 status and the canonical CP02 OperatorView fixture", async () => {
  const broker = brokerFixture();
  const { adapter, bridge } = await acceptedBridge(broker);

  const connected = await bridge.connect();
  const status = await bridge.status();
  const snapshot = await bridge.snapshot({
    schemaVersion: SNAPSHOT_QUERY_SCHEMA,
    schema: OPERATOR_VIEW_SCHEMA,
  });

  assert.equal(connected.state, "learner-unavailable");
  assert.equal(connected.serviceLive, true);
  assert.equal(status.state, "healthy");
  assert.equal(snapshot.schema_version, OPERATOR_VIEW_SCHEMA);
  assert.equal(snapshot.meta.run.run_id, "fixture-run");
  assert.equal(JSON.stringify(connected).includes("session"), false);
  await bridge.disconnect();
  adapter.close();
  assert.deepEqual(broker.calls, ["connect", "status", "disconnect", "close"]);
});

test("missing CP01 service becomes disconnected state without leaking broker errors", async () => {
  const broker = brokerFixture({ fail: true });
  const { adapter, bridge } = await acceptedBridge(broker);

  assert.deepEqual(await bridge.connect(), {
    ...disconnectedStatus(),
    connectionEpoch: 1,
  });
  assert.deepEqual(await bridge.status(), disconnectedStatus());
  adapter.close();
});

test("accepted CP01 boundary refuses CP02 operations the service does not support", async () => {
  const broker = brokerFixture();
  const { adapter, bridge } = await acceptedBridge(broker);
  await bridge.connect();

  await assert.rejects(
    bridge.command({ schemaVersion: "bilqis.bamf.mission-control.operator-action-request/v1" }),
    /BAMF_GUI20_CP01_OPERATION_UNSUPPORTED/,
  );
  await assert.rejects(
    bridge.dryRun({ schemaVersion: "bilqis.bamf.mission-control.operator-action-request/v1" }),
    /BAMF_GUI20_CP01_OPERATION_UNSUPPORTED/,
  );
  await assert.rejects(
    bridge.receipt("receipt:fixture"),
    /BAMF_GUI20_CP01_OPERATION_UNSUPPORTED/,
  );
  await assert.rejects(
    bridge.subscribe(() => {}),
    /BAMF_GUI20_CONTROL_PLANE_METHOD_UNAVAILABLE:subscribe/,
  );
  adapter.close();
});
