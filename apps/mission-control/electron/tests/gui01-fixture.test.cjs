"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const { ControlPlaneBridge } = require("../control-plane-bridge.cjs");
const {
  BOOTSTRAP_QUERY_SCHEMA,
  BOOTSTRAP_SNAPSHOT_SCHEMA,
  GUI01_FIXTURE_VALIDATORS,
  createGui01FixtureAdapter,
} = require("../gui01-fixture.cjs");

test("GUI01 bootstrap fixture crosses the same typed bridge as future CP02 snapshots", async () => {
  const bridge = new ControlPlaneBridge(
    createGui01FixtureAdapter(),
    GUI01_FIXTURE_VALIDATORS,
  );
  const connected = await bridge.connect();
  const snapshot = await bridge.snapshot({
    schemaVersion: BOOTSTRAP_QUERY_SCHEMA,
    objectRef: "shell-bootstrap",
  });

  assert.equal(connected.state, "FIXTURE");
  assert.equal(snapshot.schemaVersion, BOOTSTRAP_SNAPSHOT_SCHEMA);
  assert.equal(snapshot.context.runId, "fixture:prometheus-disposable");
  assert.equal(JSON.stringify(connected).includes("fixtureSession"), false);
});

test("GUI01 fixture refuses to invent command, dry-run or receipt semantics", async () => {
  const bridge = new ControlPlaneBridge(
    createGui01FixtureAdapter(),
    GUI01_FIXTURE_VALIDATORS,
  );
  await bridge.connect();

  await assert.rejects(
    bridge.command({ schemaVersion: "future/v1", action: "train" }),
    /BAMF_GUI20_GUI01_FIXTURE_OPERATION_UNAVAILABLE/,
  );
  await assert.rejects(
    bridge.dryRun({ schemaVersion: "future/v1", action: "preflight" }),
    /BAMF_GUI20_GUI01_FIXTURE_OPERATION_UNAVAILABLE/,
  );
  await assert.rejects(
    bridge.receipt("receipt:future"),
    /BAMF_GUI20_GUI01_FIXTURE_OPERATION_UNAVAILABLE/,
  );
});
