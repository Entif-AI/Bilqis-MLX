"use strict";

const MAX_DEPTH = 12;
const MAX_ARRAY_ITEMS = 4096;
const MAX_OBJECT_KEYS = 256;
const MAX_STRING_LENGTH = 64 * 1024;

const FORBIDDEN_RENDERER_KEYS = Object.freeze(new Set([
  "argv",
  "authorization",
  "commandline",
  "credential",
  "credentials",
  "cwd",
  "env",
  "environment",
  "executable",
  "file",
  "filename",
  "filepath",
  "path",
  "privatekey",
  "rundir",
  "script",
  "secret",
  "sessioncapability",
  "sessiontoken",
  "shell",
]));

const SECRET_OUTPUT_KEYS = Object.freeze(new Set([
  "authorization",
  "credential",
  "credentials",
  "privatekey",
  "secret",
  "sessioncapability",
  "sessiontoken",
]));

function invalid(reason) {
  const error = new TypeError(`BAMF_GUI20_IPC_ARGUMENT_INVALID:${reason}`);
  error.code = "BAMF_GUI20_IPC_ARGUMENT_INVALID";
  throw error;
}

function unsafeOutput(reason) {
  const error = new TypeError(`BAMF_GUI20_RENDERER_PAYLOAD_UNSAFE:${reason}`);
  error.code = "BAMF_GUI20_RENDERER_PAYLOAD_UNSAFE";
  throw error;
}

function isPlainObject(value) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return false;
  }
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function normalizedKey(key) {
  return key.replace(/[-_]/g, "").toLowerCase();
}

function assertSafeValue(value, options = {}, depth = 0, seen = new Set()) {
  const {
    forbiddenKeys = FORBIDDEN_RENDERER_KEYS,
    rejectForbiddenKeys = true,
    output = false,
  } = options;

  if (depth > MAX_DEPTH) {
    (output ? unsafeOutput : invalid)("MAX_DEPTH");
  }
  if (value === null || typeof value === "boolean" || typeof value === "number") {
    if (typeof value === "number" && !Number.isFinite(value)) {
      (output ? unsafeOutput : invalid)("NON_FINITE_NUMBER");
    }
    return value;
  }
  if (typeof value === "string") {
    if (value.length > MAX_STRING_LENGTH) {
      (output ? unsafeOutput : invalid)("STRING_TOO_LARGE");
    }
    return value;
  }
  if (typeof value === "undefined") {
    (output ? unsafeOutput : invalid)("UNDEFINED");
  }
  if (typeof value === "function" || typeof value === "symbol" || typeof value === "bigint") {
    (output ? unsafeOutput : invalid)("NON_JSON_VALUE");
  }
  if (seen.has(value)) {
    (output ? unsafeOutput : invalid)("CYCLIC_VALUE");
  }
  seen.add(value);
  try {
    if (Array.isArray(value)) {
      if (value.length > MAX_ARRAY_ITEMS) {
        (output ? unsafeOutput : invalid)("ARRAY_TOO_LARGE");
      }
      for (const item of value) {
        assertSafeValue(item, options, depth + 1, seen);
      }
      return value;
    }
    if (!isPlainObject(value)) {
      (output ? unsafeOutput : invalid)("NON_PLAIN_OBJECT");
    }
    const keys = Object.keys(value);
    if (keys.length > MAX_OBJECT_KEYS) {
      (output ? unsafeOutput : invalid)("OBJECT_TOO_LARGE");
    }
    for (const [key, child] of Object.entries(value)) {
      const normalized = normalizedKey(key);
      if (rejectForbiddenKeys && forbiddenKeys.has(normalized)) {
        (output ? unsafeOutput : invalid)(`FORBIDDEN_KEY:${key}`);
      }
      assertSafeValue(child, options, depth + 1, seen);
    }
    return value;
  } finally {
    seen.delete(value);
  }
}

function assertRendererRequest(value) {
  if (!isPlainObject(value)) {
    invalid("REQUEST_OBJECT_REQUIRED");
  }
  return assertSafeValue(value);
}

function assertRendererSafePayload(value) {
  return assertSafeValue(value, {
    forbiddenKeys: SECRET_OUTPUT_KEYS,
    rejectForbiddenKeys: true,
    output: true,
  });
}

function assertStableRef(value) {
  if (typeof value !== "string" || value.length === 0 || value.length > 256) {
    invalid("STABLE_REF_REQUIRED");
  }
  if (value.includes("..") || value.includes("\\") || value.startsWith("/") ||
      value.startsWith("~") || /^file:/i.test(value)) {
    invalid("STABLE_REF_NOT_PATH");
  }
  if (!/^[A-Za-z0-9][A-Za-z0-9._:/@-]*$/.test(value)) {
    invalid("STABLE_REF_INVALID");
  }
  return value;
}

module.exports = {
  FORBIDDEN_RENDERER_KEYS,
  SECRET_OUTPUT_KEYS,
  assertRendererRequest,
  assertRendererSafePayload,
  assertStableRef,
  isPlainObject,
};
