const path = require("node:path");
const { app, BrowserWindow, ipcMain } = require("electron");
const OPERATOR_VIEW_FIXTURE = require("./fixtures/operator-view-v1.json");

const BOOTSTRAP_STATE = Object.freeze({
  context: OPERATOR_VIEW_FIXTURE,
  selection: null,
});

function createWindow() {
  const window = new BrowserWindow({
    width: 1440,
    height: 920,
    minWidth: 760,
    minHeight: 620,
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  window.loadFile(path.join(__dirname, "renderer", "index.html"));
}

app.whenReady().then(() => {
  ipcMain.handle("bamf:shell-bootstrap", () => BOOTSTRAP_STATE);
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
