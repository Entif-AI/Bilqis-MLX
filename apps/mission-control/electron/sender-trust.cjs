"use strict";

function normalizedDocumentUrl(raw) {
  if (typeof raw !== "string" || raw.length === 0) {
    return null;
  }
  try {
    const value = new URL(raw);
    value.hash = "";
    return value.href;
  } catch (_error) {
    return null;
  }
}

function createTrustedSender(rendererUrl) {
  const expected = normalizedDocumentUrl(rendererUrl);
  if (expected === null) {
    throw new TypeError("BAMF_GUI20_RENDERER_URL_INVALID");
  }
  return (event) => {
    const candidate = event?.senderFrame?.url;
    return normalizedDocumentUrl(candidate) === expected;
  };
}

function requireTrustedSender(isTrustedSender, event) {
  if (!isTrustedSender(event)) {
    const error = new Error("BAMF_GUI20_UNTRUSTED_IPC_SENDER");
    error.code = "BAMF_GUI20_UNTRUSTED_IPC_SENDER";
    throw error;
  }
}

module.exports = { createTrustedSender, normalizedDocumentUrl, requireTrustedSender };
