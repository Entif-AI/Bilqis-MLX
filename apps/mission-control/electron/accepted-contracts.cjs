"use strict";

const CP01_STATUS_SCHEMA = "bamf.gui20.cp01-status/v1";
const CP01_PROTOCOL_VERSION = "bilqis.bamf.control-plane/v1";
const OPERATOR_VIEW_SCHEMA = "bilqis.bamf.mission-control.operator-view/v1";
const SNAPSHOT_QUERY_SCHEMA = "bamf.gui20.operator-view-query/v1";
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

function createAcceptedValidators(assertOperatorView, frameContracts) {
  if (typeof assertOperatorView !== "function") {
    throw new TypeError("BAMF_GUI20_OPERATOR_VIEW_VALIDATOR_REQUIRED");
  }
  return Object.freeze({
    publicStatus: validateStatus,
    snapshotRequest(value) {
      if (frameContracts && value?.schemaVersion === frameContracts.FRAME_QUERY) {
        return frameContracts.assertFrameRequest(value);
      }
      if (!exactKeys(value, ["schemaVersion", "schema"]) ||
          value.schemaVersion !== SNAPSHOT_QUERY_SCHEMA || value.schema !== OPERATOR_VIEW_SCHEMA) {
        invalid("SNAPSHOT_REQUEST");
      }
      return value;
    },
    dryRunRequest: unavailable,
    commandRequest: unavailable,
    receiptRef: unavailable,
    response(method, value, request) {
      if (method === "status") return validateStatus(value);
      if (method === "snapshot") {
        if (frameContracts && request?.schemaVersion === frameContracts.FRAME_QUERY) {
          const page = frameContracts.assertFramePage(value);
          if (!frameContracts.sameFrameRequest(request, page.request)) invalid("FRAME_REQUEST_MISMATCH");
          return page;
        }
        return assertOperatorView(value);
      }
      unavailable();
    },
    event: unavailable,
  });
}

module.exports = {
  CP01_STATUS_SCHEMA,
  OPERATOR_VIEW_SCHEMA,
  SNAPSHOT_QUERY_SCHEMA,
  createAcceptedValidators,
};
