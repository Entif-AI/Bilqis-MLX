export const CACHED_OPERATOR_VIEW_KEY = "bilqis.mc.cached-operator-view/v1";
const CACHE_SCHEMA = "bilqis.mission-control.cached-operator-view/v1";

const profiles = {
  live: ["Live service", "Current control-plane context is live and mutation may be offered through the accepted command contract.", "status", "FRESH", true, true],
  loading: ["Loading", "Establishing the local control-plane session and requesting a verified snapshot.", "status", "UNKNOWN", false, false],
  progressive: ["Progressive data", "Verified data is arriving incrementally. Missing fields remain explicitly incomplete.", "status", "UNKNOWN", false, true],
  empty: ["Empty", "The verified scope contains no records. Empty is not unavailable or denied.", "status", "FRESH", false, true],
  stale: ["Stale", "The last verified context is retained for inspection but is not current enough for mutation.", "status", "STALE", false, true],
  partial: ["Partial", "Only part of the requested evidence is available. Missing evidence remains explicit.", "status", "STALE", false, true],
  offline: ["Offline", "The local service is disconnected. Verified cached or previously received evidence is inspection-only.", "alert", "DISCONNECTED", false, true],
  denied: ["Denied", "The current session is not authorized for this surface. No mutation is offered.", "alert", "DISCONNECTED", false, true],
  revoked: ["Revoked", "Previously available authority was revoked. Existing evidence may be inspected, but no action may proceed.", "alert", "DISCONNECTED", false, true],
  unavailable: ["Unavailable", "The requested service or evidence surface is not available. This is distinct from an empty result.", "alert", "UNKNOWN", false, false],
  "incompatible-version": ["Incompatible version", "The renderer and local service cannot establish a compatible contract. Inspection is limited to verified prior evidence.", "alert", "DISCONNECTED", false, true],
  timeout: ["Timeout", "The request did not complete in time. Existing verified context is preserved without claiming a terminal outcome.", "alert", "STALE", false, true],
  "duplicate-action": ["Duplicate action", "The command identity already exists. Read the existing operation receipt instead of repeating the effect.", "alert", "FRESH", false, true],
  "session-restarting": ["Session restarting", "The renderer session is being re-established. Current investigation context is preserved where safe.", "status", "STALE", false, true],
  "service-restarting": ["Service restarting", "The local control-plane service is restarting. Learner failure is not inferred from this UI condition.", "status", "STALE", false, true],
  "historical-unavailable": ["Historical reconstruction unavailable", "The requested historical state cannot be reconstructed from retained evidence.", "alert", "UNKNOWN", false, true],
  "malformed-payload": ["Malformed payload", "A payload failed the accepted Mission Control contract and was not rendered as trusted evidence.", "alert", "UNKNOWN", false, true],
  "unsupported-payload": ["Unsupported payload", "The payload version or record type is not supported by this renderer.", "alert", "UNKNOWN", false, true],
  "outcome-unknown": ["Outcome unknown", "A consequential operation may have executed, but its postcondition has not been proven. No automatic retry is offered.", "alert", "STALE", false, true],
  unknown: ["State unknown", "The renderer cannot yet classify the current service posture. Mutation remains unavailable.", "status", "UNKNOWN", false, true],
};

function makeProfile(id, snapshotAvailable = false, snapshotSource = "none") {
  const raw = profiles[id] ?? profiles.unknown;
  const [label, description, role, freshness, mutationAllowed, inspectWhenSnapshot] = raw;
  const inspectionAllowed = snapshotAvailable && inspectWhenSnapshot;
  const historical = id !== "live" && snapshotAvailable;
  return Object.freeze({
    id,
    label,
    description,
    role,
    freshness,
    mutationAllowed: mutationAllowed && snapshotAvailable,
    inspectionAllowed,
    historical,
    snapshotAvailable,
    snapshotSource,
    reconnectAvailable: new Set([
      "offline", "stale", "timeout", "session-restarting", "service-restarting",
      "unavailable", "unknown",
    ]).has(id),
  });
}

export function defensiveState(id, options = {}) {
  return makeProfile(id, Boolean(options.snapshotAvailable), options.snapshotSource ?? "none");
}

export function defensiveStateForConnection(connectionState, options = {}) {
  const key = String(connectionState ?? "unknown").toLowerCase();
  const mapped = {
    healthy: "live",
    live: "live",
    stale: "stale",
    partial: "partial",
    disconnected: "offline",
    offline: "offline",
    unauthorized: "denied",
    denied: "denied",
    revoked: "revoked",
    "incompatible-version": "incompatible-version",
    timeout: "timeout",
    "session-restarting": "session-restarting",
    "service-restarting": "service-restarting",
    unavailable: "unavailable",
  }[key] ?? "unknown";
  return defensiveState(mapped, options);
}

export function defensiveStateForError(error, options = {}) {
  const text = `${error?.code ?? ""}:${error?.message ?? ""}`.toLowerCase();
  let id = "unavailable";
  if (text.includes("schema_unsupported") || text.includes("unsupported")) id = "unsupported-payload";
  else if (text.includes("operator_view_invalid") || text.includes("malformed") || text.includes("invalid_record")) id = "malformed-payload";
  else if (text.includes("timeout") || text.includes("timed out")) id = "timeout";
  else if (text.includes("incompatible")) id = "incompatible-version";
  else if (text.includes("unauthorized") || text.includes("denied")) id = "denied";
  return defensiveState(id, options);
}

export function defensiveStateIds() {
  return Object.keys(profiles).filter((id) => id !== "live" && id !== "unknown");
}

export function defensiveCatalogMarkup() {
  return defensiveStateIds().map((id) => {
    const profile = defensiveState(id, { snapshotAvailable: true, snapshotSource: "fixture" });
    return `<div class="state-surface" data-state="${profile.id}" data-role="${profile.role}"><strong>${profile.label}</strong><small>${profile.description}</small></div>`;
  }).join("");
}

export function defensiveBannerMarkup(profile) {
  const source = profile.snapshotAvailable
    ? profile.snapshotSource === "cache"
      ? "Cached verified snapshot · inspection only"
      : profile.historical
        ? "Last verified snapshot · inspection only"
        : "Current verified snapshot"
    : "No verified snapshot available";
  const mutation = profile.mutationAllowed ? "Operator mutation contract available" : "Mutation unavailable";
  const reconnect = profile.reconnectAvailable
    ? `<button type="button" data-reconnect>Reconnect</button>`
    : "";
  return `<div class="defensive-copy"><strong>${profile.label}</strong><span>${profile.description}</span><small>${source} · ${mutation}</small></div>${reconnect}`;
}

export function cacheOperatorView(storage, operatorView, cachedAt = Date.now()) {
  if (!storage || typeof storage.setItem !== "function") return;
  if (!Number.isSafeInteger(cachedAt) || cachedAt < 0) return;
  storage.setItem(CACHED_OPERATOR_VIEW_KEY, JSON.stringify({
    schema: CACHE_SCHEMA,
    cachedAt,
    operatorView,
  }));
}

export function loadCachedOperatorView(storage) {
  if (!storage || typeof storage.getItem !== "function") return null;
  const raw = storage.getItem(CACHED_OPERATOR_VIEW_KEY);
  if (typeof raw !== "string" || raw.length === 0 || raw.length > 1024 * 1024) return null;
  try {
    const parsed = JSON.parse(raw);
    if (
      parsed?.schema !== CACHE_SCHEMA ||
      !Number.isSafeInteger(parsed.cachedAt) || parsed.cachedAt < 0 ||
      !parsed.operatorView || typeof parsed.operatorView !== "object" || Array.isArray(parsed.operatorView)
    ) return null;
    return Object.freeze({ cachedAt: parsed.cachedAt, operatorView: parsed.operatorView });
  } catch (_error) {
    return null;
  }
}
