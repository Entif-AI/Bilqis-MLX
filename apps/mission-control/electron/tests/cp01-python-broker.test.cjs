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

test("Node broker receives a real CP04 EventEnvelope through the private event bridge", async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "bilqis-gui03-events-"));
  const socketPath = path.join(root, "cp.sock");
  const runDir = path.join(root, "missing-run");
  const python = process.env.BILQIS_PYTHON || "python3";
  const script = `
from pathlib import Path
import time
from bilqis_mlx.control_plane import ControlPlaneService
from bilqis_mlx.control_plane.event_stream import EventFamily
from bilqis_mlx.control_plane.tests.support import start_service
from bilqis_mlx.mission_control.events import LearningEpisode
from bilqis_mlx.mission_control.tests.samples import SAMPLES
service = ControlPlaneService(Path(${JSON.stringify(runDir)}), Path(${JSON.stringify(socketPath)}), event_heartbeat_seconds=0.02)
thread = start_service(service)
try:
    time.sleep(0.35)
    episode = next(item for item in SAMPLES if type(item) is LearningEpisode)
    service.publish_event(EventFamily.LESSON_VISIT_COMPLETED, episode)
    time.sleep(1.0)
finally:
    service.shutdown()
    thread.join(2)
`;
  const service = spawn(python, ["-B", "-c", script], {
    cwd: REPO_ROOT, shell: false, stdio: ["ignore", "ignore", "ignore"],
  });
  const broker = new Cp01PythonBroker({
    pythonExecutable: python,
    cwd: REPO_ROOT,
    env: { ...process.env, BILQIS_CONTROL_PLANE_SOCKET: socketPath },
  });
  try {
    await waitForPath(socketPath, service);
    const observed = await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error("GUI03_EVENT_TIMEOUT")), 2500);
      const unsubscribe = broker.subscribe((event) => {
        clearTimeout(timeout);
        unsubscribe();
        resolve(event);
      });
    });
    assert.equal(observed.schema_version, "bilqis.bamf.mission-control.event-envelope/v1");
    assert.equal(observed.event_family, "lesson.visit.completed");
    assert.equal(observed.payload_record_id, "episode");
    assert.equal(JSON.stringify(observed).includes(socketPath), false);
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
