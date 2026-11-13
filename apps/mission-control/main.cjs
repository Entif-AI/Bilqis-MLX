"use strict";

const path = require("node:path");
const { app, BrowserWindow, ipcMain, net, protocol } = require("electron");

const { ControlPlaneBridge } = require("./electron/control-plane-bridge.cjs");
const {
  GUI01_FIXTURE_VALIDATORS,
  createGui01FixtureAdapter,
} = require("./electron/gui01-fixture.cjs");
const { registerMissionControlIpc } = require("./electron/main-ipc.cjs");
const { registerRendererSchemePrivileges } = require("./electron/renderer-location.cjs");
const { registerMissionControlProtocol } = require("./electron/renderer-protocol.cjs");
const { createMissionControlWindow } = require("./electron/window-security.cjs");

registerRendererSchemePrivileges(protocol);

let disposeIpc = null;

function createWindow() {
  const { window } = createMissionControlWindow({
    BrowserWindow,
    preloadPath: path.join(__dirname, "electron", "preload.cjs"),
    browserWindowOptions: {
      width: 1440,
      height: 920,
      minWidth: 760,
      minHeight: 620,
    },
  });
  const bridge = new ControlPlaneBridge(
    createGui01FixtureAdapter(),
    GUI01_FIXTURE_VALIDATORS,
  );
  disposeIpc = registerMissionControlIpc({
    ipcMain,
    bridge,
    trustedWebContents: window.webContents,
  });
  window.once("closed", () => {
    disposeIpc?.();
    disposeIpc = null;
    void bridge.disconnect();
  });
  return window;
}

app.whenReady().then(() => {
  registerMissionControlProtocol({
    protocol,
    net,
    assetRoot: path.join(__dirname, "renderer"),
  });
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
