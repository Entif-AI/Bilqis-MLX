"use strict";

function typedRecord(value) {
  if (!value || typeof value !== "object" || Array.isArray(value) ||
      typeof value.schemaVersion !== "string" || value.schemaVersion.length === 0) {
    const error = new TypeError("FIXTURE_CP02_RECORD_INVALID");
    error.code = "FIXTURE_CP02_RECORD_INVALID";
    throw error;
  }
  return value;
}

function receiptRef(value) {
  if (typeof value !== "string" || !value.startsWith("receipt:")) {
    const error = new TypeError("FIXTURE_CP02_RECEIPT_REF_INVALID");
    error.code = "FIXTURE_CP02_RECEIPT_REF_INVALID";
    throw error;
  }
  return value;
}

function event(value) {
  if (!value || typeof value !== "object" || typeof value.cursor !== "string") {
    const error = new TypeError("FIXTURE_CP02_EVENT_INVALID");
    error.code = "FIXTURE_CP02_EVENT_INVALID";
    throw error;
  }
  return value;
}

const FIXTURE_VALIDATORS = Object.freeze({
  snapshotRequest: typedRecord,
  dryRunRequest: typedRecord,
  commandRequest: typedRecord,
  receiptRef,
  event,
});

module.exports = { FIXTURE_VALIDATORS };
