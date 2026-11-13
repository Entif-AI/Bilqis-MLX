"use strict";

const BOOTSTRAP_QUERY_SCHEMA = "bamf.gui01.bootstrap-query.fixture/v1";
const BOOTSTRAP_SNAPSHOT_SCHEMA = "bamf.gui01.bootstrap-snapshot.fixture/v1";
const FIXTURE_STATUS_SCHEMA = "bamf.gui01.status.fixture/v1";

const BOOTSTRAP_STATE = Object.freeze({
  context: Object.freeze({
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
  }),
  selection: null,
});

function invalid(reason) {
  const error = new TypeError(`BAMF_GUI20_GUI01_FIXTURE_INVALID:${reason}`);
  error.code = "BAMF_GUI20_GUI01_FIXTURE_INVALID";
  throw error;
}

function unavailable() {
  const error = new Error("BAMF_GUI20_GUI01_FIXTURE_OPERATION_UNAVAILABLE");
  error.code = "BAMF_GUI20_GUI01_FIXTURE_OPERATION_UNAVAILABLE";
  throw error;
}

function exactKeys(value, keys) {
  return value && typeof value === "object" && !Array.isArray(value) &&
    Object.keys(value).length === keys.length && keys.every((key) => key in value);
}

const GUI01_FIXTURE_VALIDATORS = Object.freeze({
  publicStatus(value) {
    if (!exactKeys(value, ["schemaVersion", "state", "protocolVersion"]) ||
        value.schemaVersion !== FIXTURE_STATUS_SCHEMA || value.state !== "FIXTURE" ||
        value.protocolVersion !== "gui01-fixture/v1") {
      invalid("PUBLIC_STATUS");
    }
    return value;
  },
  snapshotRequest(value) {
    if (!exactKeys(value, ["schemaVersion", "objectRef"]) ||
        value.schemaVersion !== BOOTSTRAP_QUERY_SCHEMA || value.objectRef !== "shell-bootstrap") {
      invalid("SNAPSHOT_REQUEST");
    }
    return value;
  },
  dryRunRequest: unavailable,
  commandRequest: unavailable,
  receiptRef: unavailable,
  response(method, value) {
    if (method === "status" && exactKeys(value, ["schemaVersion", "state"]) &&
        value.schemaVersion === FIXTURE_STATUS_SCHEMA && value.state === "FIXTURE") {
      return value;
    }
    if (method === "snapshot" && exactKeys(value, ["schemaVersion", "context", "selection"]) &&
        value.schemaVersion === BOOTSTRAP_SNAPSHOT_SCHEMA) {
      return value;
    }
    invalid(`RESPONSE:${method}`);
  },
  event: unavailable,
});

function createGui01FixtureAdapter() {
  const session = Object.freeze({ fixtureSession: Symbol("gui01-fixture-session") });
  return {
    async connect() {
      return {
        session,
        publicStatus: {
          schemaVersion: FIXTURE_STATUS_SCHEMA,
          state: "FIXTURE",
          protocolVersion: "gui01-fixture/v1",
        },
      };
    },
    async disconnect() {},
    async status(current) {
      if (current !== session) invalid("SESSION");
      return { schemaVersion: FIXTURE_STATUS_SCHEMA, state: "FIXTURE" };
    },
    async snapshot(current) {
      if (current !== session) invalid("SESSION");
      return {
        schemaVersion: BOOTSTRAP_SNAPSHOT_SCHEMA,
        context: BOOTSTRAP_STATE.context,
        selection: BOOTSTRAP_STATE.selection,
      };
    },
    async subscribe(current) {
      if (current !== session) invalid("SESSION");
      return () => {};
    },
  };
}

module.exports = {
  BOOTSTRAP_QUERY_SCHEMA,
  BOOTSTRAP_SNAPSHOT_SCHEMA,
  GUI01_FIXTURE_VALIDATORS,
  createGui01FixtureAdapter,
};
