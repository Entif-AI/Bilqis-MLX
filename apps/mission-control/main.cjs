const path = require("node:path");
const { app, BrowserWindow, ipcMain } = require("electron");

const BOOTSTRAP_STATE = Object.freeze({
  context: {
    runId: "fixture:prometheus-disposable",
    mode: "LIVE",
    generation: 44238,
    checkpoint: "fixture-checkpoint",
    topologyId: "bamf-0.2-fixture",
    factoryRelease: "fixture-release",
    semanticRelease: "fixture-semantic",
    optimizerStep: 0,
    admissionLease: "NOT_HELD",
    correctionFrontier: "fixture-frontier",
    freshness: "FRESH",
    resourceHealth: "NOMINAL",
  },
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
