"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const { ControlPlaneBridge } = require("../control-plane-bridge.cjs");

function adapterFixture() {
  const calls = [];
  let listener;
  let sessionNumber = 0;
  return {
    calls,
    get listener() {
      return listener;
    },
    async connect() {
      sessionNumber += 1;
      const session = { token: `secret-${sessionNumber}`, id: sessionNumber };
      calls.push(["connect", session]);
      return {
        session,
        publicStatus: {
          state: "HEALTHY",
          protocolVersion: "cp01/v1",
          runId: "run-1",
        },
      };
    },
    async disconnect(session) {
      calls.push(["disconnect", session]);
    },
    async status(session) {
      calls.push(["status", session]);
      return { state: "HEALTHY", runId: "run-1" };
    },
    async snapshot(session, request) {
      calls.push(["snapshot", session, request]);
      return { schemaVersion: "snapshot/v1", objectRef: request.objectRef };
    },
    async dryRun(session, request) {
      calls.push(["dryRun", session, request]);
      return { state: "READY", requestId: request.requestId };
    },
    async command(session, request) {
      calls.push(["command", session, request]);
      return { state: "ACCEPTED", requestId: request.requestId };
    },
    async receipt(session, ref) {
      calls.push(["receipt", session, ref]);
      return { ref, verified: true };
    },
    async subscribe(session, next) {
      calls.push(["subscribe", session]);
      listener = next;
      return () => {
        calls.push(["unsubscribe", session]);
        listener = null;
      };
    },
  };
}

test("connection session and credential material remain main-process only", async () => {
  const adapter = adapterFixture();
  const bridge = new ControlPlaneBridge(adapter);

  const publicStatus = await bridge.connect();

  assert.deepEqual(publicStatus, {
    state: "HEALTHY",
    protocolVersion: "cp01/v1",
    runId: "run-1",
    connectionEpoch: 1,
  });
  assert.equal(JSON.stringify(publicStatus).includes("secret-1"), false);
  await bridge.status();
  assert.equal(adapter.calls.at(-1)[1].token, "secret-1");
});

test("unsafe service output is rejected before it reaches the renderer", async () => {
  const adapter = adapterFixture();
  adapter.status = async () => ({ state: "HEALTHY", sessionToken: "leak" });
  const bridge = new ControlPlaneBridge(adapter);
  await bridge.connect();

  await assert.rejects(
    bridge.status(),
    /BAMF_GUI20_RENDERER_PAYLOAD_UNSAFE:FORBIDDEN_KEY:sessionToken/,
  );
});

test("unsafe handshake payload is rejected and its fresh session is disconnected", async () => {
  const adapter = adapterFixture();
  adapter.connect = async () => ({
    session: { token: "secret" },
    publicStatus: { state: "HEALTHY", credential: "leak" },
  });
  const bridge = new ControlPlaneBridge(adapter);

  await assert.rejects(
    bridge.connect(),
    /BAMF_GUI20_RENDERER_PAYLOAD_UNSAFE:FORBIDDEN_KEY:credential/,
  );
  assert.equal(adapter.calls.some(([name]) => name === "disconnect"), true);
  await assert.rejects(bridge.status(), /BAMF_GUI20_CONTROL_PLANE_NOT_CONNECTED/);
});

test("reconnect invalidates old subscriptions and obsolete session state", async () => {
  const adapter = adapterFixture();
  const bridge = new ControlPlaneBridge(adapter);
  const observed = [];

  await bridge.connect();
  await bridge.subscribe((event) => observed.push(event));
  const staleListener = adapter.listener;
  staleListener({ cursor: "event:1" });

  const second = await bridge.connect();
  staleListener({ cursor: "event:stale" });

  assert.equal(second.connectionEpoch, 2);
  assert.deepEqual(observed, [{ cursor: "event:1" }]);
  assert.equal(adapter.calls.filter(([name]) => name === "unsubscribe").length, 1);
  assert.equal(adapter.calls.filter(([name]) => name === "disconnect").length, 1);
});

test("bridge forwards typed data but rejects path and process escape hatches", async () => {
  const adapter = adapterFixture();
  const bridge = new ControlPlaneBridge(adapter);
  await bridge.connect();

  assert.deepEqual(
    await bridge.snapshot({ schemaVersion: "snapshot-query/v1", objectRef: "capability:A.ADD" }),
    { schemaVersion: "snapshot/v1", objectRef: "capability:A.ADD" },
  );
  assert.deepEqual(
    await bridge.dryRun({ schemaVersion: "action/v1", requestId: "r1" }),
    { state: "READY", requestId: "r1" },
  );
  assert.deepEqual(
    await bridge.command({ schemaVersion: "action/v1", requestId: "r2" }),
    { state: "ACCEPTED", requestId: "r2" },
  );
  assert.deepEqual(await bridge.receipt("receipt:abc"), { ref: "receipt:abc", verified: true });

  await assert.rejects(
    bridge.command({ argv: ["python3", "trainer.py"] }),
    /BAMF_GUI20_IPC_ARGUMENT_INVALID:FORBIDDEN_KEY:argv/,
  );
  await assert.rejects(
    bridge.snapshot({ runDir: "/tmp/student" }),
    /BAMF_GUI20_IPC_ARGUMENT_INVALID:FORBIDDEN_KEY:runDir/,
  );
  await assert.rejects(
    bridge.receipt("../../etc/passwd"),
    /BAMF_GUI20_IPC_ARGUMENT_INVALID:STABLE_REF_NOT_PATH/,
  );
});
