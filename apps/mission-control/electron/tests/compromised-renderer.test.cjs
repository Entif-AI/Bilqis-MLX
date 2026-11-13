"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const { CHANNELS } = require("../channels.cjs");
const { ControlPlaneBridge } = require("../control-plane-bridge.cjs");
const { registerMissionControlIpc } = require("../main-ipc.cjs");
const { installPreloadBridge } = require("../preload-bridge.cjs");

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
  const bridge = new ControlPlaneBridge(adapter);
  registerMissionControlIpc({ ipcMain, bridge, rendererUrl: "file:///app/index.html" });

  const event = {
    senderFrame: { url: "file:///app/index.html" },
    sender: {
      id: 1,
      send() {},
      isDestroyed() { return false; },
      once() {},
    },
  };
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
  let api;
  installPreloadBridge({
    exposeInMainWorld(_name, exposed) { api = exposed; },
  }, ipcRenderer);

  const connected = await api.connect();
  assert.equal(JSON.stringify(connected).includes("main-only-token"), false);
  assert.equal(api.readFile, undefined);
  assert.equal(api.exec, undefined);
  assert.equal(api.invoke, undefined);

  assert.throws(
    () => api.querySnapshot({ path: "/etc/passwd" }),
    /BAMF_GUI20_IPC_ARGUMENT_INVALID/,
  );
  assert.throws(
    () => api.requestCommand({ argv: ["python3", "-m", "bilqis_mlx.cli", "train"] }),
    /BAMF_GUI20_IPC_ARGUMENT_INVALID/,
  );
  assert.throws(
    () => api.requestDryRun({ shell: "python3 -m bilqis_mlx.cli train" }),
    /BAMF_GUI20_IPC_ARGUMENT_INVALID/,
  );
  await assert.rejects(
    ipcRenderer.invoke("fs:read", "/etc/passwd"),
    /NO_HANDLER:fs:read/,
  );
  await assert.rejects(
    ipcRenderer.invoke("shell:exec", "python3 -m bilqis_mlx.cli train"),
    /NO_HANDLER:shell:exec/,
  );

  assert.deepEqual(adapterCalls, []);
  assert.equal(handlers.has(CHANNELS.command), true);
});
