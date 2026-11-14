"use strict";

const CP01_STATUS_SCHEMA = "bamf.gui20.cp01-status/v1";
const CP01_PROTOCOL_VERSION = "bilqis.bamf.control-plane/v1";
const OPERATOR_VIEW_SCHEMA = "bilqis.bamf.mission-control.operator-view/v1";
const SNAPSHOT_QUERY_SCHEMA = "bamf.gui20.operator-view-query/v1";
const QUERY_REQUEST_SCHEMA = "bilqis.bamf.control-plane.query/v1";
const QUERY_PAGE_SCHEMA = "bilqis.bamf.control-plane.query-page/v1";
const QUERY_ERROR_SCHEMA = "bamf.gui07.query-error/v1";
const QUERY_FAMILIES = new Set([
  "run", "school", "capability", "episode", "generation", "semantic", "frame",
  "neural", "memory", "teacher", "salience", "correction", "resource",
  "reference", "links",
]);
const QUERY_MODES = new Set(["current", "historical"]);
const QUERY_STATES = new Set([
  "PRESENT", "EMPTY", "MISSING", "UNAVAILABLE", "PARTIAL", "STALE", "DENIED", "UNKNOWN",
]);
const COVERAGE_STATES = new Set(["COMPLETE", "PARTIAL", "UNKNOWN", "NOT_APPLICABLE"]);
const CP01_STATES = new Set([
  "connecting", "healthy", "degraded", "incompatible-version", "unauthorized",
  "learner-unavailable", "service-restarting", "stale", "disconnected",
]);

function invalid(reason) {
  const error = new TypeError(`BAMF_GUI20_ACCEPTED_CONTRACT_INVALID:${reason}`);
  error.code = "BAMF_GUI20_ACCEPTED_CONTRACT_INVALID";
  throw error;
}

function unavailable() {
  const error = new Error("BAMF_GUI20_CP01_OPERATION_UNSUPPORTED");
  error.code = "BAMF_GUI20_CP01_OPERATION_UNSUPPORTED";
  throw error;
}

function exactKeys(value, keys) {
  return value && typeof value === "object" && !Array.isArray(value) &&
    Object.keys(value).length === keys.length && keys.every((key) => key in value);
}

function validateStatus(value) {
  const keys = [
    "schemaVersion", "state", "protocolVersion", "serviceLive", "serviceReady",
    "learnerReady", "learnerActive",
  ];
  const protocolVersionValid = value?.state === "incompatible-version"
    ? typeof value?.protocolVersion === "string" && value.protocolVersion.length > 0
    : value?.protocolVersion === CP01_PROTOCOL_VERSION;
  if (!exactKeys(value, keys) || value.schemaVersion !== CP01_STATUS_SCHEMA ||
      !protocolVersionValid || !CP01_STATES.has(value.state) ||
      typeof value.serviceLive !== "boolean" || typeof value.serviceReady !== "boolean" ||
      typeof value.learnerReady !== "boolean" ||
      (value.learnerActive !== null && typeof value.learnerActive !== "boolean")) {
    invalid("CP01_STATUS");
  }
  return value;
}

function nullableName(value) {
  return value === null || (typeof value === "string" && value.length > 0 &&
    value !== "latest" && !value.includes("\n"));
}

function validateQueryRequest(value) {
  const keys = [
    "schema", "family", "mode", "run_id", "record_id", "schema_version",
    "generation", "frontier_id", "as_of", "reference", "cursor", "limit",
  ];
  if (!exactKeys(value, keys) || value.schema !== QUERY_REQUEST_SCHEMA ||
      !QUERY_FAMILIES.has(value.family) || !QUERY_MODES.has(value.mode) ||
      ![value.run_id, value.record_id, value.schema_version, value.frontier_id,
        value.reference, value.cursor].every(nullableName) ||
      (value.generation !== null && (!Number.isSafeInteger(value.generation) || value.generation < 0)) ||
      (value.as_of !== null && (!Number.isSafeInteger(value.as_of) || value.as_of < 0)) ||
      !Number.isSafeInteger(value.limit) || value.limit < 1 || value.limit > 32) {
    invalid("QUERY_REQUEST");
  }
  if (value.mode === "historical" &&
      [value.generation, value.frontier_id, value.as_of, value.record_id].every((item) => item === null)) {
    invalid("QUERY_HISTORICAL_IDENTITY");
  }
  if (value.family === "reference" && value.reference === null) invalid("QUERY_REFERENCE");
  if (value.family === "links" && value.record_id === null) invalid("QUERY_LINKS");
  return value;
}

function validateQueryResponse(value) {
  if (exactKeys(value, ["schema", "accepted", "reason"]) &&
      value.schema === QUERY_ERROR_SCHEMA && value.accepted === false &&
      typeof value.reason === "string" && value.reason.length > 0) {
    return value;
  }
  const keys = [
    "schema", "query_id", "request", "family", "mode", "state", "coverage",
    "total_matches", "returned", "truncated", "next_cursor", "records", "markers",
    "links", "accepted",
  ];
  if (!exactKeys(value, keys) || value.schema !== QUERY_PAGE_SCHEMA || value.accepted !== true ||
      typeof value.query_id !== "string" || value.query_id.length !== 64 ||
      !QUERY_FAMILIES.has(value.family) || !QUERY_MODES.has(value.mode) ||
      !QUERY_STATES.has(value.state) || !COVERAGE_STATES.has(value.coverage) ||
      !Number.isSafeInteger(value.total_matches) || value.total_matches < 0 ||
      !Number.isSafeInteger(value.returned) || value.returned < 0 ||
      typeof value.truncated !== "boolean" ||
      (value.next_cursor !== null && typeof value.next_cursor !== "string") ||
      !Array.isArray(value.records) || !Array.isArray(value.markers) || !Array.isArray(value.links)) {
    invalid("QUERY_RESPONSE");
  }
  validateQueryRequest(value.request);
  return value;
}

function createAcceptedValidators(assertOperatorView) {
  if (typeof assertOperatorView !== "function") {
    throw new TypeError("BAMF_GUI20_OPERATOR_VIEW_VALIDATOR_REQUIRED");
  }
  return Object.freeze({
    publicStatus: validateStatus,
    snapshotRequest(value) {
      if (!exactKeys(value, ["schemaVersion", "schema"]) ||
          value.schemaVersion !== SNAPSHOT_QUERY_SCHEMA || value.schema !== OPERATOR_VIEW_SCHEMA) {
        invalid("SNAPSHOT_REQUEST");
      }
      return value;
    },
    queryRequest: validateQueryRequest,
    dryRunRequest: unavailable,
    commandRequest: unavailable,
    receiptRef: unavailable,
    response(method, value) {
      if (method === "status") return validateStatus(value);
      if (method === "snapshot") return assertOperatorView(value);
      if (method === "query") return validateQueryResponse(value);
      unavailable();
    },
    event: unavailable,
  });
}

module.exports = {
  CP01_STATUS_SCHEMA,
  OPERATOR_VIEW_SCHEMA,
  SNAPSHOT_QUERY_SCHEMA,
  QUERY_REQUEST_SCHEMA,
  QUERY_PAGE_SCHEMA,
  QUERY_ERROR_SCHEMA,
  createAcceptedValidators,
};
