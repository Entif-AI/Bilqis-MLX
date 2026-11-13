"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const {
  SECURITY_PREFERENCES,
  createMissionControlWindow,
  createSecureWindowOptions,
  hardenWebContents,
  securityDiagnostic,
} = require("../window-security.cjs");

function webContentsFixture() {
  const handlers = new Map();
  let windowOpenHandler;
  let permissionRequest;
  let permissionCheck;
  return {
    handlers,
    session: {
      setPermissionRequestHandler(handler) {
        permissionRequest = handler;
      },
      setPermissionCheckHandler(handler) {
        permissionCheck = handler;
      },
    },
    on(name, handler) {
      handlers.set(name, handler);
    },
    setWindowOpenHandler(handler) {
      windowOpenHandler = handler;
    },
    get windowOpenHandler() {
      return windowOpenHandler;
    },
    get permissionRequest() {
      return permissionRequest;
    },
    get permissionCheck() {
      return permissionCheck;
    },
  };
}

test("security preferences override attempts to weaken the renderer boundary", () => {
  const options = createSecureWindowOptions("/app/preload.cjs", {
    width: 1200,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
      sandbox: false,
      webviewTag: true,
      allowRunningInsecureContent: true,
    },
  });

  assert.equal(options.width, 1200);
  assert.equal(options.webPreferences.preload, "/app/preload.cjs");
  for (const [key, expected] of Object.entries(SECURITY_PREFERENCES)) {
    assert.equal(options.webPreferences[key], expected, key);
  }
  assert.deepEqual(securityDiagnostic(options), {
    schemaVersion: "bamf.gui20.security-diagnostic/v1",
    checks: {
      contextIsolation: true,
      sandbox: true,
      nodeIntegration: true,
      nodeIntegrationInWorker: true,
      nodeIntegrationInSubFrames: true,
      webviewTag: true,
      webSecurity: true,
      allowRunningInsecureContent: true,
      preload: true,
    },
    passed: true,
  });
});

test("navigation, new windows, webviews and permissions fail closed", () => {
  const contents = webContentsFixture();
  const rendererUrl = "file:///Applications/Bilqis/MissionControl/index.html";
  hardenWebContents(contents, rendererUrl);

  let prevented = false;
  contents.handlers.get("will-navigate")(
    { preventDefault() { prevented = true; } },
    "https://evil.example/phish",
  );
  assert.equal(prevented, true);

  prevented = false;
  contents.handlers.get("will-navigate")(
    { preventDefault() { prevented = true; } },
    `${rendererUrl}#capability=A.ADD`,
  );
  assert.equal(prevented, false);

  let webviewPrevented = false;
  contents.handlers.get("will-attach-webview")({
    preventDefault() { webviewPrevented = true; },
  });
  assert.equal(webviewPrevented, true);
  assert.deepEqual(contents.windowOpenHandler({ url: "https://evil.example" }), { action: "deny" });

  let permission;
  contents.permissionRequest({}, "camera", (value) => { permission = value; });
  assert.equal(permission, false);
  assert.equal(contents.permissionCheck({}, "clipboard-read"), false);
});

test("window factory applies the hardened preferences before loading renderer content", () => {
  const instances = [];
  function BrowserWindow(options) {
    this.options = options;
    this.webContents = webContentsFixture();
    this.loaded = null;
    this.loadURL = (url) => { this.loaded = url; };
    instances.push(this);
  }

  const rendererUrl = "file:///Applications/Bilqis/MissionControl/index.html";
  const result = createMissionControlWindow({
    BrowserWindow,
    preloadPath: "/Applications/Bilqis/MissionControl/preload.cjs",
    rendererUrl,
    browserWindowOptions: { show: false },
  });

  assert.equal(instances.length, 1);
  assert.equal(result.window.loaded, rendererUrl);
  assert.equal(result.window.options.show, false);
  assert.equal(result.window.options.webPreferences.nodeIntegration, false);
  assert.equal(result.window.options.webPreferences.contextIsolation, true);
  assert.equal(result.window.options.webPreferences.sandbox, true);
  assert.equal(result.diagnostic.passed, true);
});
