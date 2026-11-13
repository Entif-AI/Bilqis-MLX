"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { spawn } = require("node:child_process");
const { once } = require("node:events");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const { Cp01PythonBroker } = require("../cp01-python-broker.cjs");

const REPO_ROOT = path.resolve(__dirname, "../../../..");

async function waitForPath(target, process) {
  const deadline = Date.now() + 3000;
  while (!fs.existsSync(target) && Date.now() < deadline) {
    if (process.exitCode !== null) {
      throw new Error(`CP01_SERVICE_EXITED:${process.exitCode}`);
    }
    await new Promise((resolve) => setTimeout(resolve, 10));
  }
  assert.equal(fs.existsSync(target), true, "CP01 socket did not become ready");
}

test("Node broker reaches accepted CP01 through the private Python bridge", async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "bilqis-gui20-"));
  const socketPath = path.join(root, "cp.sock");
  const runDir = path.join(root, "missing-run");
  const python = process.env.BILQIS_PYTHON || "python3";
  const service = spawn(
    python,
    [
      "-B", "-m", "bilqis_mlx.control_plane",
      "--run-dir", runDir,
      "--socket", socketPath,
    ],
    { cwd: REPO_ROOT, shell: false, stdio: ["ignore", "ignore", "ignore"] },
  );
  const broker = new Cp01PythonBroker({
    pythonExecutable: python,
    cwd: REPO_ROOT,
    env: { ...process.env, BILQIS_CONTROL_PLANE_SOCKET: socketPath },
  });

  try {
    await waitForPath(socketPath, service);
    const connected = await broker.connect();
    const status = await broker.status();
    const disconnected = await broker.disconnect();

    assert.equal(connected.protocolVersion, "bilqis.bamf.control-plane/v1");
    assert.equal(connected.state, "learner-unavailable");
    assert.equal(connected.serviceLive, true);
    assert.equal(status.serviceReady, true);
    assert.equal(disconnected.state, "disconnected");
    const rendererVisible = JSON.stringify({ connected, status, disconnected });
    assert.equal(rendererVisible.includes(socketPath), false);
    assert.equal(rendererVisible.includes(runDir), false);
    assert.equal(rendererVisible.includes("session_id"), false);
  } finally {
    broker.close();
    if (service.exitCode === null) {
      service.kill("SIGINT");
      await once(service, "exit");
    }
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test("broker requests fail closed within a bounded timeout when Python wedges", async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "bilqis-gui20-hung-"));
  const executable = path.join(root, "hung-python");
  fs.writeFileSync(executable, "#!/bin/sh\ncat >/dev/null\n", { mode: 0o700 });
  const broker = new Cp01PythonBroker({
    pythonExecutable: executable,
    cwd: REPO_ROOT,
    requestTimeoutMs: 25,
  });
  const started = Date.now();
  try {
    await assert.rejects(broker.disconnect(), /BAMF_GUI20_CP01_UNAVAILABLE/);
    assert.ok(Date.now() - started < 1000, "broker timeout was not bounded");
  } finally {
    broker.close();
    fs.rmSync(root, { recursive: true, force: true });
  }
});
