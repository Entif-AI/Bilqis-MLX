"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const { CHANNELS } = require("../channels.cjs");
const { GLOBAL_NAME, installPreloadBridge } = require("../preload-bridge.cjs");

function fakeRenderer() {
  const invoked = [];
  const listeners = new Map();
  return {
    invoked,
    listeners,
    invoke(channel, ...args) {
      invoked.push([channel, ...args]);
      return Promise.resolve({ channel });
    },
    on(channel, listener) {
      listeners.set(channel, listener);
    },
    removeListener(channel, listener) {
      if (listeners.get(channel) === listener) {
        listeners.delete(channel);
      }
    },
  };
}

test("preload exposes only the enumerated Mission Control capability surface", () => {
  const renderer = fakeRenderer();
  let exposed;
  const contextBridge = {
    exposeInMainWorld(name, api) {
      exposed = { name, api };
    },
  };

  const api = installPreloadBridge(contextBridge, renderer);

  assert.equal(exposed.name, GLOBAL_NAME);
  assert.equal(exposed.api, api);
  assert.deepEqual(Object.keys(api).sort(), [
    "connect",
    "fetchReceipt",
    "querySnapshot",
    "requestCommand",
    "requestDryRun",
    "status",
    "subscribeEvents",
  ]);
  assert.equal(Object.isFrozen(api), true);
  assert.equal(api.invoke, undefined);
  assert.equal(api.send, undefined);
  assert.equal(api.readFile, undefined);
  assert.equal(api.shell, undefined);
  assert.equal(api.spawn, undefined);
});

test("preload rejects filesystem and shell-shaped requests before IPC", async () => {
  const renderer = fakeRenderer();
  const api = installPreloadBridge({ exposeInMainWorld() {} }, renderer);

  assert.throws(
    () => api.querySnapshot({ path: "/etc/passwd" }),
    /BAMF_GUI20_IPC_ARGUMENT_INVALID:FORBIDDEN_KEY:path/,
  );
  assert.throws(
    () => api.requestCommand({ argv: ["python3", "-m", "bilqis_mlx.cli"] }),
    /BAMF_GUI20_IPC_ARGUMENT_INVALID:FORBIDDEN_KEY:argv/,
  );
  assert.throws(
    () => api.requestDryRun({ shell: "rm -rf ~" }),
    /BAMF_GUI20_IPC_ARGUMENT_INVALID:FORBIDDEN_KEY:shell/,
  );
  assert.throws(
    () => api.fetchReceipt("../../private-key"),
    /BAMF_GUI20_IPC_ARGUMENT_INVALID:STABLE_REF_NOT_PATH/,
  );
  assert.deepEqual(renderer.invoked, []);
});

test("preload invokes only fixed channels and unsubscribes its fixed event listener", async () => {
  const renderer = fakeRenderer();
  const api = installPreloadBridge({ exposeInMainWorld() {} }, renderer);

  await api.connect();
  await api.status();
  await api.querySnapshot({ schemaVersion: "fixture/v1", objectRef: "run:one" });
  await api.requestDryRun({ schemaVersion: "fixture/v1", action: "preflight" });
  await api.requestCommand({ schemaVersion: "fixture/v1", action: "resume" });
  await api.fetchReceipt("receipt:abc-123");

  const events = [];
  const unsubscribe = api.subscribeEvents((value) => events.push(value));
  await new Promise((resolve) => setImmediate(resolve));
  renderer.listeners.get(CHANNELS.event)?.({}, { cursor: "event:1" });
  await unsubscribe();

  assert.deepEqual(events, [{ cursor: "event:1" }]);
  assert.equal(renderer.listeners.has(CHANNELS.event), false);
  assert.deepEqual(renderer.invoked.map(([channel]) => channel), [
    CHANNELS.connect,
    CHANNELS.status,
    CHANNELS.snapshot,
    CHANNELS.dryRun,
    CHANNELS.command,
    CHANNELS.receipt,
    CHANNELS.eventsSubscribe,
    CHANNELS.eventsUnsubscribe,
  ]);
});
