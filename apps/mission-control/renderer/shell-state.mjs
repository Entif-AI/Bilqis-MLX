export const DESTINATIONS = Object.freeze([
  ["mission-control", "Mission Control"],
  ["school", "School"],
  ["learning", "Learning"],
  ["atlas", "Atlas"],
  ["model", "Model"],
  ["memory", "Memory"],
  ["teacher", "Teacher"],
  ["corrections", "Corrections"],
  ["lineage", "Lineage"],
  ["resources", "Resources"],
  ["evidence", "Evidence"],
  ["operate", "Operate"],
]);

export const INSPECTOR_OWNERS = Object.freeze({
  capability: "school",
  episode: "learning",
  semantic: "atlas",
  memory: "memory",
  checkpoint: "lineage",
  evidence: "evidence",
  correction: "corrections",
  warning: "resources",
});

export const OPERATOR_VIEW_SCHEMA = "bilqis.bamf.mission-control.operator-view/v1";

export function normalizeContext(raw = {}) {
  if (raw.schema_version !== OPERATOR_VIEW_SCHEMA || !raw.meta?.run) {
    throw new TypeError("MISSION_CONTROL_OPERATOR_VIEW_SCHEMA_UNSUPPORTED");
  }
  const run = raw.meta.run;
  return Object.freeze({
    runId: run.run_id,
    mode: "LIVE",
    generation: run.generation,
    checkpoint: run.generation_manifest_sha256,
    topologyId: run.topology_sha256,
    factoryRelease: run.factory_release_sha256,
    semanticRelease: run.semantic_release_sha256,
    optimizerStep: "UNKNOWN",
    admissionLease: "UNKNOWN",
    correctionFrontier: "UNKNOWN",
    freshness: raw.meta.coverage === "COMPLETE" ? "FRESH" : "STALE",
    resourceHealth: "UNKNOWN",
    schemaVersion: raw.schema_version,
    recordId: raw.meta.record_id,
  });
}

export function createShellState(context, route = {}) {
  const destinations = new Set(DESTINATIONS.map(([id]) => id));
  const view = destinations.has(route.view) ? route.view : "mission-control";
  return {
    context: normalizeContext(context),
    view,
    selected: route.selected ?? null,
    inspectorOpen: Boolean(route.selected),
  };
}

export function navigate(state, view, selected = null) {
  const destinations = new Set(DESTINATIONS.map(([id]) => id));
  if (!destinations.has(view)) return state;
  return {
    ...state,
    view,
    selected,
    inspectorOpen: selected !== null,
  };
}

export function inspect(state, selected) {
  return { ...state, selected, inspectorOpen: Boolean(selected) };
}

export function openSelectionOwner(state) {
  if (!state.selected) return state;
  const owner = INSPECTOR_OWNERS[state.selected.kind];
  return owner ? navigate(state, owner, state.selected) : state;
}

export function withContext(state, nextContext) {
  return { ...state, context: normalizeContext(nextContext) };
}

export function shellPosture(context) {
  if (context.mode === "HISTORICAL") return "historical";
  if (context.freshness === "STALE" || context.freshness === "DISCONNECTED") return "stale";
  return "live";
}
