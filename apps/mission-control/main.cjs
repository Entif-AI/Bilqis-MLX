"use strict";

const path = require("node:path");
const { app, BrowserWindow, ipcMain, net, protocol } = require("electron");

const { AcceptedControlPlaneAdapter } = require(
  "./electron/accepted-control-plane-adapter.cjs",
);
const { createAcceptedValidators } = require("./electron/accepted-contracts.cjs");
const { ControlPlaneBridge } = require("./electron/control-plane-bridge.cjs");
const { registerMissionControlIpc } = require("./electron/main-ipc.cjs");
const { registerRendererSchemePrivileges } = require("./electron/renderer-location.cjs");
const { registerMissionControlProtocol } = require("./electron/renderer-protocol.cjs");
const { createMissionControlWindow } = require("./electron/window-security.cjs");

registerRendererSchemePrivileges(protocol);

async function createWindow() {
  const { assertOperatorView } = await import("./renderer/shell-state.mjs");
  const adapter = new AcceptedControlPlaneAdapter();
  const bridge = new ControlPlaneBridge(
    adapter,
    createAcceptedValidators(assertOperatorView),
  );
  const { window, loadRenderer } = createMissionControlWindow({
    BrowserWindow,
    preloadPath: path.join(__dirname, "electron", "preload.cjs"),
    browserWindowOptions: {
      width: 1440,
      height: 920,
      minWidth: 760,
      minHeight: 620,
    },
  });
  const disposeIpc = registerMissionControlIpc({
    ipcMain,
    bridge,
    trustedWebContents: window.webContents,
  });
  await loadRenderer();
  window.once("closed", () => {
    disposeIpc();
    void bridge.disconnect().finally(() => adapter.close());
  });
  return window;
}

app.whenReady().then(async () => {
  registerMissionControlProtocol({
    protocol,
    net,
    assetRoot: path.join(__dirname, "renderer"),
  });
  await createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      void createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
