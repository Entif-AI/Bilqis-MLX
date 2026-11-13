"use strict";

const { RENDERER_ENTRY_URL, normalizedRendererDocument } = require("./renderer-location.cjs");

const SECURITY_PREFERENCES = Object.freeze({
  contextIsolation: true,
  sandbox: true,
  nodeIntegration: false,
  nodeIntegrationInWorker: false,
  nodeIntegrationInSubFrames: false,
  webviewTag: false,
  webSecurity: true,
  allowRunningInsecureContent: false,
});

function createSecureWindowOptions(preloadPath, callerOptions = {}) {
  if (typeof preloadPath !== "string" || preloadPath.length === 0) {
    throw new TypeError("BAMF_GUI20_PRELOAD_PATH_REQUIRED");
  }
  const callerPreferences = callerOptions.webPreferences ?? {};
  return {
    ...callerOptions,
    webPreferences: {
      ...callerPreferences,
      preload: preloadPath,
      ...SECURITY_PREFERENCES,
    },
  };
}

function isTrustedRendererDocument(candidate) {
  return normalizedRendererDocument(candidate) === RENDERER_ENTRY_URL;
}

function hardenWebContents(webContents) {
  if (!webContents || typeof webContents.on !== "function" ||
      typeof webContents.setWindowOpenHandler !== "function") {
    throw new TypeError("BAMF_GUI20_WEB_CONTENTS_REQUIRED");
  }
  webContents.on("will-navigate", (event, targetUrl) => {
    if (!isTrustedRendererDocument(targetUrl)) {
      event.preventDefault();
    }
  });
  webContents.on("will-attach-webview", (event) => event.preventDefault());
  webContents.setWindowOpenHandler(() => ({ action: "deny" }));

  const session = webContents.session;
  session?.setPermissionRequestHandler?.((_contents, _permission, callback) => callback(false));
  session?.setPermissionCheckHandler?.(() => false);
}

function securityDiagnostic(windowOptions) {
  const preferences = windowOptions?.webPreferences ?? {};
  const checks = Object.fromEntries(Object.entries(SECURITY_PREFERENCES).map(
    ([key, expected]) => [key, preferences[key] === expected]));
  checks.preload = typeof preferences.preload === "string" && preferences.preload.length > 0;
  return Object.freeze({
    schemaVersion: "bamf.gui20.security-diagnostic/v1",
    checks: Object.freeze(checks),
    passed: Object.values(checks).every(Boolean),
  });
}

function createMissionControlWindow({
  BrowserWindow,
  preloadPath,
  browserWindowOptions = {},
}) {
  if (typeof BrowserWindow !== "function") {
    throw new TypeError("BAMF_GUI20_BROWSER_WINDOW_REQUIRED");
  }
  const options = createSecureWindowOptions(preloadPath, browserWindowOptions);
  const diagnostic = securityDiagnostic(options);
  if (!diagnostic.passed) {
    throw new Error("BAMF_GUI20_SECURITY_DIAGNOSTIC_FAILED");
  }
  const window = new BrowserWindow(options);
  hardenWebContents(window.webContents);
  window.loadURL(RENDERER_ENTRY_URL);
  return Object.freeze({ window, diagnostic });
}

module.exports = {
  SECURITY_PREFERENCES,
  createMissionControlWindow,
  createSecureWindowOptions,
  hardenWebContents,
  isTrustedRendererDocument,
  securityDiagnostic,
};
