"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const { CHANNELS, HANDLER_CHANNELS } = require("../channels.cjs");
const { ControlPlaneBridge } = require("../control-plane-bridge.cjs");
const { registerMissionControlIpc } = require("../main-ipc.cjs");

function ipcMainFixture() {
  const handlers = new Map();
  return {
    handlers,
    handle(channel, handler) {
      if (handlers.has(channel)) {
        throw new Error(`duplicate:${channel}`);
      }
      handlers.set(channel, handler);
    },
    removeHandler(channel) {
      handlers.delete(channel);
    },
  };
}

function senderFixture(url = "file:///app/index.html") {
  const sent = [];
  const onceHandlers = new Map();
  return {
    event: {
      senderFrame: { url },
      sender: {
        id: 17,
        send(channel, payload) { sent.push([channel, payload]); },
        isDestroyed() { return false; },
        once(name, handler) { onceHandlers.set(name, handler); },
      },
    },
    sent,
    onceHandlers,
  };
}

function adapterFixture() {
  let listener;
  return {
    async connect() {
      return {
        session: { token: "main-only" },
        publicStatus: { state: "HEALTHY", protocolVersion: "cp01/v1" },
      };
    },
    async status() { return { state: "HEALTHY" }; },
    async snapshot(_session, request) { return { request }; },
    async dryRun(_session, request) { return { request }; },
    async command(_session, request) { return { request }; },
    async receipt(_session, ref) { return { ref }; },
    async subscribe(_session, next) {
      listener = next;
      return () => { listener = null; };
    },
    emit(payload) { listener?.(payload); },
  };
}

test("main registers only the enumerated request channels", () => {
  const ipcMain = ipcMainFixture();
  const bridge = new ControlPlaneBridge(adapterFixture());
  const dispose = registerMissionControlIpc({
    ipcMain,
    bridge,
    rendererUrl: "file:///app/index.html",
  });

  assert.deepEqual([...ipcMain.handlers.keys()], [...HANDLER_CHANNELS]);
  assert.equal(ipcMain.handlers.has("shell:exec"), false);
  assert.equal(ipcMain.handlers.has("fs:read"), false);
  assert.equal(ipcMain.handlers.has("ipc:invoke"), false);

  dispose();
  assert.equal(ipcMain.handlers.size, 0);
});

test("untrusted renderer origins cannot invoke even valid channels", async () => {
  const ipcMain = ipcMainFixture();
  const bridge = new ControlPlaneBridge(adapterFixture());
  registerMissionControlIpc({ ipcMain, bridge, rendererUrl: "file:///app/index.html" });
  const { event } = senderFixture("https://evil.example/index.html");

  await assert.rejects(
    ipcMain.handlers.get(CHANNELS.connect)(event),
    /BAMF_GUI20_UNTRUSTED_IPC_SENDER/,
  );
});

test("trusted renderer uses typed handlers and cannot smuggle file or shell arguments", async () => {
  const ipcMain = ipcMainFixture();
  const adapter = adapterFixture();
  const bridge = new ControlPlaneBridge(adapter);
  registerMissionControlIpc({ ipcMain, bridge, rendererUrl: "file:///app/index.html" });
  const { event } = senderFixture();

  await ipcMain.handlers.get(CHANNELS.connect)(event);
  assert.deepEqual(await ipcMain.handlers.get(CHANNELS.status)(event), { state: "HEALTHY" });
  await assert.rejects(
    ipcMain.handlers.get(CHANNELS.snapshot)(event, { path: "/etc/passwd" }),
    /BAMF_GUI20_IPC_ARGUMENT_INVALID:FORBIDDEN_KEY:path/,
  );
  await assert.rejects(
    ipcMain.handlers.get(CHANNELS.command)(event, { shell: "open -a Terminal" }),
    /BAMF_GUI20_IPC_ARGUMENT_INVALID:FORBIDDEN_KEY:shell/,
  );
});

test("event subscription only forwards renderer-safe control-plane events", async () => {
  const ipcMain = ipcMainFixture();
  const adapter = adapterFixture();
  const bridge = new ControlPlaneBridge(adapter);
  registerMissionControlIpc({ ipcMain, bridge, rendererUrl: "file:///app/index.html" });
  const sender = senderFixture();

  await ipcMain.handlers.get(CHANNELS.connect)(sender.event);
  await ipcMain.handlers.get(CHANNELS.eventsSubscribe)(sender.event);
  adapter.emit({ cursor: "event:1", state: "RUNNING" });
  assert.deepEqual(sender.sent, [[CHANNELS.event, { cursor: "event:1", state: "RUNNING" }]]);

  assert.throws(
    () => adapter.emit({ cursor: "event:2", sessionToken: "leak" }),
    /BAMF_GUI20_RENDERER_PAYLOAD_UNSAFE:FORBIDDEN_KEY:sessionToken/,
  );
  await ipcMain.handlers.get(CHANNELS.eventsUnsubscribe)(sender.event);
  adapter.emit({ cursor: "event:3" });
  assert.equal(sender.sent.length, 1);
});
