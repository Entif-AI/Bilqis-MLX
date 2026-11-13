"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const { CHANNELS } = require("../channels.cjs");
const { ControlPlaneBridge } = require("../control-plane-bridge.cjs");
const { registerMissionControlIpc } = require("../main-ipc.cjs");
const { RENDERER_ENTRY_URL, RENDERER_ORIGIN } = require("../renderer-location.cjs");
const { loadSandboxedPreload } = require("./_preload-fixture.cjs");
const { FIXTURE_VALIDATORS } = require("./_contract-fixture.cjs");

test("compromised renderer cannot turn the preload bridge into file or trainer execution", async () => {
  const handlers = new Map();
  const ipcMain = {
    handle(channel, handler) { handlers.set(channel, handler); },
    removeHandler(channel) { handlers.delete(channel); },
  };
  const adapterCalls = [];
  const adapter = {
    async connect() {
      return {
        session: { sessionToken: "main-only-token" },
        publicStatus: { state: "HEALTHY", protocolVersion: "cp01/v1" },
      };
    },
    async command(_session, request) {
      adapterCalls.push(request);
      return { state: "ACCEPTED" };
    },
    async dryRun(_session, request) {
      adapterCalls.push(request);
      return { state: "READY" };
    },
    async status() { return { state: "HEALTHY" }; },
    async snapshot() { return { schemaVersion: "fixture/v1" }; },
    async receipt() { return { ref: "receipt:fixture" }; },
    async subscribe() { return () => {}; },
  };
  const bridge = new ControlPlaneBridge(adapter, FIXTURE_VALIDATORS);

  const frame = { url: RENDERER_ENTRY_URL, origin: RENDERER_ORIGIN };
  frame.top = frame;
  const sender = {
    id: 1,
    mainFrame: frame,
    send() {},
    isDestroyed() { return false; },
    once() {},
  };
  const event = {
    senderFrame: frame,
    sender,
  };
  registerMissionControlIpc({ ipcMain, bridge, trustedWebContents: sender });
  const listeners = new Map();
  const ipcRenderer = {
    invoke(channel, ...args) {
      const handler = handlers.get(channel);
      if (!handler) {
        return Promise.reject(new Error(`NO_HANDLER:${channel}`));
      }
      return handler(event, ...args);
    },
    on(channel, listener) { listeners.set(channel, listener); },
    removeListener(channel) { listeners.delete(channel); },
  };
  const api = loadSandboxedPreload(ipcRenderer).api;

  const connected = await api.connect();
  assert.equal(JSON.stringify(connected).includes("main-only-token"), false);
  assert.equal(api.readFile, undefined);
  assert.equal(api.exec, undefined);
  assert.equal(api.invoke, undefined);

  await assert.rejects(
    ipcRenderer.invoke("fs:read", "/etc/passwd"),
    /NO_HANDLER:fs:read/,
  );
  await assert.rejects(
    ipcRenderer.invoke("shell:exec", "python3 -m bilqis_mlx.cli train"),
    /NO_HANDLER:shell:exec/,
  );

  await api.requestCommand({
    schemaVersion: "cp02-fixture/v1",
    requestId: "request-1",
    action: "owner-action",
  });
  assert.deepEqual(adapterCalls, [{
    schemaVersion: "cp02-fixture/v1",
    requestId: "request-1",
    action: "owner-action",
  }]);
  assert.equal(handlers.has(CHANNELS.command), true);
});
